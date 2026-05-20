"""Minimal HTTP client for the HG Insights MCP server (JSON-RPC tools/call)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class HgMcpError(Exception):
    """Raised when the MCP server returns an error or is unreachable."""


def _parse_tool_text(text: str, tool_name: str) -> Any:
    """Parse MCP text content; HG sometimes returns empty or plain-text messages."""
    cleaned = (text or "").strip()
    if not cleaned:
        return {}

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract embedded JSON object/array from mixed content.
        for pattern in (r"(\{.*\})", r"(\[.*\])"):
            match = re.search(pattern, cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        raise HgMcpError(
            f"Tool '{tool_name}' returned non-JSON text: {cleaned[:300]}"
        )


class HgMcpClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or self._resolve_mcp_url()).rstrip("/")
        if not self.base_url:
            raise HgMcpError(
                "HG MCP URL is not configured. Set HG_MCP_URL or configure "
                "hg-insights in ~/.cursor/mcp.json."
            )
        self._request_id = 0
        self._initialized = False

    @staticmethod
    def _resolve_mcp_url() -> str:
        env_url = os.environ.get("HG_MCP_URL", "").strip()
        if env_url:
            return env_url
        mcp_path = Path.home() / ".cursor" / "mcp.json"
        if mcp_path.is_file():
            try:
                data = json.loads(mcp_path.read_text(encoding="utf-8"))
                return data.get("mcpServers", {}).get("hg-insights", {}).get("url", "")
            except (json.JSONDecodeError, OSError):
                pass
        return ""

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HgMcpError(f"MCP HTTP error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise HgMcpError(f"Cannot reach MCP server: {exc}") from exc

        # Some endpoints may return SSE-style payloads; take the last JSON line.
        if raw.strip().startswith("event:") or raw.strip().startswith("data:"):
            for line in reversed(raw.splitlines()):
                line = line.strip()
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line.startswith("{") or line.startswith("["):
                    try:
                        data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
            else:
                raise HgMcpError(f"Invalid SSE JSON from MCP: {raw[:500]}")
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise HgMcpError(f"Invalid JSON from MCP: {raw[:500]}") from exc

        if "error" in data:
            err = data["error"]
            message = err.get("message", str(err))
            raise HgMcpError(f"MCP error: {message}")
        return data

    def initialize(self) -> None:
        if self._initialized:
            return
        self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "seller-profile-cli", "version": "0.1.0"},
                },
            }
        )
        self._initialized = True

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        self.initialize()
        data = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
        )
        result = data.get("result", {})
        if result.get("isError"):
            message = ""
            for block in result.get("content") or []:
                if block.get("type") == "text":
                    message += block.get("text") or ""
            raise HgMcpError(message.strip() or f"Tool '{name}' returned isError=true")

        if "structuredContent" in result and result["structuredContent"] is not None:
            return result["structuredContent"]

        content = result.get("content") or []
        texts = [
            block.get("text", "")
            for block in content
            if block.get("type") == "text" and block.get("text") is not None
        ]
        if texts:
            combined = "\n".join(texts).strip()
            return _parse_tool_text(combined, name)

        return result

    def call_tool_safe(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> tuple[Any | None, str | None]:
        """Return (payload, error_message). Never raises."""
        try:
            return self.call_tool(name, arguments), None
        except (HgMcpError, json.JSONDecodeError) as exc:
            return None, str(exc)
