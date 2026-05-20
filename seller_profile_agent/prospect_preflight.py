"""Preflight prospects: ensure HG can score them (avoid search bucket duplicates)."""

from __future__ import annotations

import re
from typing import Any

from hg_client import HgMcpClient

# Search often returns range floors, not true company-specific values.
SEARCH_REVENUE_BUCKET_FLOORS = {
    50_000_000,
    100_000_000,
    250_000_000,
    500_000_000,
    1_000_000_000,
}
SEARCH_EMPLOYEE_BUCKET_FLOORS = {200, 500, 1000, 5000, 10000}
COMPOUND_PUBLIC_SUFFIXES = {
    "co.uk",
    "org.uk",
    "ac.uk",
    "gov.uk",
    "com.br",
    "com.tr",
    "com.au",
    "co.in",
}


def normalize_hg_id(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if re.fullmatch(r"[A-Za-z0-9]{31,32}", text):
        return text
    # Scientific notation from JSON float corruption — unusable
    if "e+" in text.lower() or "e-" in text.lower():
        return None
    return None


def is_search_range_proxy(revenue: Any, employees: Any, employees_range: str | None) -> bool:
    """True when search row likely carries bucket mins, not exact firmographics."""
    try:
        rev = float(revenue) if revenue is not None else None
    except (TypeError, ValueError):
        rev = None
    try:
        emp = int(employees) if employees is not None else None
    except (TypeError, ValueError):
        emp = None

    rev_bucket = rev is not None and rev in SEARCH_REVENUE_BUCKET_FLOORS
    emp_bucket = emp is not None and emp in SEARCH_EMPLOYEE_BUCKET_FLOORS
    range_text = (employees_range or "").lower()
    above_band = "above" in range_text or "from $" in (str(revenue) if revenue else "").lower()

    return bool(rev_bucket and emp_bucket and above_band)


def resolve_canonical_domain(firmo: dict[str, Any], fallback: str) -> str:
    return (
        (firmo.get("domain") or firmo.get("website") or firmo.get("_resolved_domain") or fallback)
        .lower()
        .strip()
        .replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
    )


def _domain_candidates(search_domain: str) -> list[str]:
    """Try full domain first, then registrable/root fallbacks for subdomains."""
    domain = (search_domain or "").strip().lower().split("/")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    out: list[str] = []
    if domain:
        out.append(domain)
    parts = domain.split(".")
    if len(parts) >= 3:
        last2 = ".".join(parts[-2:])
        if last2 not in out:
            out.append(last2)
        last3 = ".".join(parts[-3:])
        if ".".join(parts[-2:]) in COMPOUND_PUBLIC_SUFFIXES and last3 not in out:
            out.append(last3)
    return out


def preflight_firmographic(
    client: HgMcpClient,
    row: dict[str, Any],
) -> dict[str, Any]:
    """
    One MCP call. Returns scorable flag + canonical firmographics for legacy callers.
    """
    search_domain = (row.get("domain") or row.get("companyDomain") or "").lower().strip()
    hg_id = normalize_hg_id(row.get("companyId"))

    if not hg_id and not search_domain:
        return {"scorable": False, "reason": "missing_domain", "search_domain": search_domain}

    attempts: list[dict[str, Any]] = []
    if hg_id:
        attempts.append({"hg_id": hg_id})
    for dom in _domain_candidates(search_domain):
        attempts.append({"companyDomain": dom})

    firmo = None
    err = None
    tried: list[str] = []
    for args in attempts:
        tried.append(str(args))
        firmo, err = client.call_tool_safe("company_firmographic", args)
        if not err and firmo and firmo.get("found"):
            break
    if err or not firmo or not firmo.get("found"):
        return {
            "scorable": False,
            "reason": f"firmographic_miss: {err or 'not found'}",
            "search_domain": search_domain,
            "tried": tried,
        }

    canonical = resolve_canonical_domain(firmo, search_domain)
    revenue = firmo.get("revenue") or firmo.get("revenueAmount")
    employees = firmo.get("employeeCount") or firmo.get("employees")
    it_spend = firmo.get("itSpend") or firmo.get("it_spend")

    try:
        rev_f = float(revenue) if revenue is not None else None
    except (TypeError, ValueError):
        rev_f = None
    try:
        emp_i = int(employees) if employees is not None else None
    except (TypeError, ValueError):
        emp_i = None

    has_size_signal = (rev_f is not None and rev_f > 0) or (emp_i is not None and emp_i > 0)
    if not has_size_signal:
        return {
            "scorable": False,
            "reason": "firmographic_no_size_fields",
            "search_domain": search_domain,
            "canonical_domain": canonical,
        }

    return {
        "scorable": True,
        "search_domain": search_domain,
        "canonical_domain": canonical,
        "hg_id": normalize_hg_id(
            (firmo.get("metadata") or {}).get("hginsights_id")
            if isinstance(firmo.get("metadata"), dict)
            else None
        )
        or hg_id,
        "firmographic": firmo,
        "revenue_usd": rev_f,
        "employee_count": emp_i,
        "it_spend_usd": float(it_spend) if it_spend else None,
        "company_name": firmo.get("name") or firmo.get("companyName") or row.get("companyName"),
    }


def select_scorable_prospects(
    client: HgMcpClient,
    candidate_rows: list[dict[str, Any]],
    prs_count: int,
    max_preflight_calls: int = 25,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Legacy helper: walk the provided candidate list until `prs_count` scorable prospects.
    The official pipeline samples before deep PRS and does not use this as a ranking step.
    """
    stats: dict[str, Any] = {
        "preflight_attempts": 0,
        "scorable_found": 0,
        "rejected": [],
        "preflight_trace": [],
    }
    selected: list[dict[str, Any]] = []

    for row in candidate_rows:
        if len(selected) >= prs_count:
            break
        if stats["preflight_attempts"] >= max_preflight_calls:
            break

        domain = (row.get("domain") or row.get("companyDomain") or "").lower().strip()
        stats["preflight_attempts"] += 1
        pf = preflight_firmographic(client, row)
        if not pf.get("scorable"):
            stats["rejected"].append(
                {"domain": row.get("domain"), "reason": pf.get("reason")}
            )
            stats["preflight_trace"].append(
                {
                    "sample_position": row.get("sample_position"),
                    "domain": domain,
                    "company_name": row.get("companyName") or row.get("company_name"),
                    "outcome": "preflight_failed",
                    "reason": pf.get("reason"),
                }
            )
            continue

        merged = {
            **row,
            "domain": pf["canonical_domain"],
            "companyDomain": pf["canonical_domain"],
            "companyName": pf.get("company_name") or row.get("companyName"),
            "revenueAmount": pf.get("revenue_usd"),
            "employeeCount": pf.get("employee_count"),
            "itSpend": pf.get("it_spend_usd"),
            "_preflight": pf,
            "_search_domain": pf.get("search_domain"),
        }
        selected.append(merged)
        stats["scorable_found"] += 1
        stats["preflight_trace"].append(
            {
                "sample_position": row.get("sample_position"),
                "domain": domain,
                "company_name": merged.get("companyName"),
                "outcome": "selected_for_deep_prs",
            }
        )

    return selected, stats
