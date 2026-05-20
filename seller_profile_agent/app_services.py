"""Shared services for the Streamlit demo app (wraps CLI pipeline logic)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cli import _output_slug
from executive_reports import write_company_prs_report
from hg_client import HgMcpClient, HgMcpError
from last_run_state import save_last_profile_run
from pipeline_cli import run_pipeline
from prs_company_cli import resolve_prospect_row
from prompt_inputs import list_products_from_profile, read_icp_user_floors
from prospect_scorer import score_prospect
from sales_insights import build_prospect_card
from score_cli import _load_binding
from seller_profile_builder import (
    build_seller_profile,
    discover_seller_product_lines,
    update_product_binding_only,
)

ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "output" / "seller_profiles"
OUTPUTS_ROOT = ROOT / "outputs"
PRS_REPORTS_DIR = ROOT / "output" / "prs_reports"


def apply_streamlit_secrets() -> None:
    """Use Streamlit Cloud secrets for HG_MCP_URL when present."""
    try:
        import streamlit as st

        url = (st.secrets.get("HG_MCP_URL") or "").strip()
        if url:
            os.environ["HG_MCP_URL"] = url
    except Exception:
        pass


def hg_connection_status() -> dict[str, Any]:
    apply_streamlit_secrets()
    try:
        client = HgMcpClient()
        url = client.base_url
        masked = url if len(url) <= 48 else f"{url[:40]}…"
        return {"ok": True, "url": masked}
    except HgMcpError as exc:
        return {"ok": False, "error": str(exc)}


def list_seller_profiles() -> list[dict[str, Any]]:
    if not PROFILE_DIR.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(PROFILE_DIR.glob("seller_profile_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            seller = payload.get("seller_profile") or payload
            sel = seller.get("selected_product") or {}
            binding = sel.get("hg_binding") or {}
            rows.append(
                {
                    "path": path,
                    "slug": path.stem.replace("seller_profile_", ""),
                    "company_name": seller.get("company_name") or path.stem,
                    "domain": seller.get("domain") or "",
                    "product_name": binding.get("hg_product_name") or sel.get("product_name") or "—",
                    "mtime": path.stat().st_mtime,
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    return rows


def profile_path_for_slug(slug: str) -> Path:
    return PROFILE_DIR / f"seller_profile_{slug.strip().lower()}.json"


def discover_company_products(company: str) -> dict[str, Any]:
    apply_streamlit_secrets()
    client = HgMcpClient()
    prefetch = discover_seller_product_lines(client, company.strip())
    slug = _output_slug(prefetch["company_name"], prefetch["domain"])
    return {
        "ok": True,
        "company_name": prefetch["company_name"],
        "domain": prefetch["domain"],
        "slug": slug,
        "products": prefetch["products"],
        "profile_path": profile_path_for_slug(slug),
        "prefetch": prefetch,
    }


def build_seller_profile_web(
    *,
    company: str,
    product_index: int,
    icp_floors: dict[str, int],
    prefetch: dict[str, Any] | None = None,
    slug: str | None = None,
    force_full: bool = False,
) -> dict[str, Any]:
    apply_streamlit_secrets()
    client = HgMcpClient()
    company = company.strip()
    guess_slug = (slug or company).strip().lower()
    profile_path = profile_path_for_slug(guess_slug)

    stored_floors = read_icp_user_floors(profile_path)
    floors_changed = icp_floors != stored_floors
    needs_full = force_full or not profile_path.is_file() or stored_floors is None or floors_changed

    if needs_full:
        path, payload = build_seller_profile(
            client, company, product_index, prefetch=prefetch, icp_floors=icp_floors
        )
    else:
        path, payload = update_product_binding_only(
            client, profile_path, product_index, icp_floors=icp_floors
        )

    seller = payload.get("seller_profile") or payload
    sel = seller.get("selected_product") or {}
    binding = sel.get("hg_binding") or {}
    product_sold = binding.get("hg_product_name") or sel.get("product_name")
    slug_final = path.stem.replace("seller_profile_", "")

    save_last_profile_run(
        company_input=company,
        company_slug=slug_final,
        product_index=product_index,
        company_name=str(seller.get("company_name") or company),
        product_name=str(product_sold or ""),
    )

    return {
        "ok": True,
        "path": path,
        "slug": slug_final,
        "company_name": seller.get("company_name"),
        "domain": seller.get("domain"),
        "product_sold": product_sold,
        "payload": payload,
    }


@dataclass
class LogCollector:
    lines: list[str] = field(default_factory=list)

    def __call__(self, msg: str) -> None:
        self.lines.append(msg)


def run_pipeline_web(
    *,
    company: str,
    product_index: int = 1,
    prs_count: int = 3,
    run_name: str | None = None,
    sample_seed: int | None = None,
    profile_slug: str | None = None,
    full_profile: bool = False,
    enrich_icp_it_spend: bool = False,
    on_log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    apply_streamlit_secrets()
    collector = LogCollector()
    log_fn = on_log or collector

    result = run_pipeline(
        company=company,
        product_index=product_index,
        prs_count=max(1, min(10, prs_count)),
        full_profile=full_profile,
        run_name=run_name,
        ask_run_name=False,
        sample_seed=sample_seed,
        profile_slug=profile_slug,
        enrich_icp_it_spend=enrich_icp_it_spend,
        log_fn=log_fn,
    )

    if isinstance(result, int):
        return {"ok": False, "exit_code": result, "logs": collector.lines}

    result["logs"] = collector.lines
    return result


def run_single_prs_web(
    *,
    profile_path: Path,
    company_query: str,
) -> dict[str, Any]:
    apply_streamlit_secrets()
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    seller = payload.get("seller_profile") or payload
    binding = _load_binding(seller)
    selected = seller.get("selected_product") or {}

    client = HgMcpClient()
    row = resolve_prospect_row(client, company_query.strip())
    prospect = score_prospect(client, row, binding)
    prospect.rank = 1

    seller_meta = {
        "slug": profile_path.stem.replace("seller_profile_", ""),
        "company_name": seller.get("company_name"),
        "target_product": selected.get("product_name"),
        "hg_product_name": binding.get("hg_product_name"),
        "hg_product_id": binding.get("hg_product_id"),
        "hg_category_name": binding.get("hg_category_name"),
        "hg_intent_topic_name": binding.get("hg_intent_topic_name"),
    }
    card = build_prospect_card(prospect, seller_meta, comparative_bullets=None)
    report_path = write_company_prs_report(PRS_REPORTS_DIR, seller_meta, seller, prospect, card)

    return {
        "ok": True,
        "report_path": report_path,
        "prospect_name": prospect.company_name,
        "domain": prospect.domain,
        "prs": round(prospect.prs, 2),
        "reliability": round(prospect.reliability_global, 4),
        "report_md": report_path.read_text(encoding="utf-8") if report_path.is_file() else "",
    }


def list_output_iterations() -> list[dict[str, Any]]:
    if not OUTPUTS_ROOT.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(OUTPUTS_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_dir():
            continue
        exec_md = path / "executive_summary.md"
        candidate_md = path / "candidate_companies.md"
        rows.append(
            {
                "name": path.name,
                "path": path,
                "has_executive": exec_md.is_file(),
                "has_candidates": candidate_md.is_file(),
                "mtime": path.stat().st_mtime,
            }
        )
    return rows


def read_text_if_exists(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""
