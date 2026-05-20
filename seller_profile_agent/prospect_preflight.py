"""Preflight prospects: ensure HG can score them (avoid search bucket duplicates)."""

from __future__ import annotations

import re
from typing import Any

from company_resolver import pick_best_search_company
from hg_client import HgMcpClient

from hg_value_parser import is_hg_bucket_range

# Search often returns range floors, not true company-specific values.
SEARCH_REVENUE_BUCKET_FLOORS = {
    10_000_000,
    25_000_000,
    50_000_000,
    100_000_000,
    250_000_000,
    500_000_000,
    1_000_000_000,
}
SEARCH_EMPLOYEE_BUCKET_FLOORS = {200, 500, 1000, 5000, 10000}


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
    if is_hg_bucket_range(revenue) or is_hg_bucket_range(employees_range):
        return True

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
    banded_employees = "from" in range_text and " to " in range_text

    return bool(rev_bucket and emp_bucket and banded_employees)


def resolve_canonical_domain(firmo: dict[str, Any], fallback: str) -> str:
    return (
        (firmo.get("domain") or firmo.get("website") or firmo.get("_resolved_domain") or fallback)
        .lower()
        .strip()
        .replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
    )


def _row_company_name(row: dict[str, Any]) -> str | None:
    name = (row.get("companyName") or row.get("company_name") or row.get("name") or "").strip()
    return name or None


def _firmographic_hg_id(firmo: dict[str, Any], fallback: str | None) -> str | None:
    meta = firmo.get("metadata")
    if isinstance(meta, dict):
        resolved = normalize_hg_id(meta.get("hginsights_id"))
        if resolved:
            return resolved
    return normalize_hg_id(fallback)


def resolve_prospect_firmographic(
    client: HgMcpClient,
    row: dict[str, Any],
) -> dict[str, Any]:
    """
    Resolve a prospect to HG firmographics with automatic fallback:
    hg_id -> search domain -> canonical domain from firmographic -> search by company name.
    """
    search_domain = (row.get("domain") or row.get("companyDomain") or "").lower().strip()
    hg_id = normalize_hg_id(row.get("companyId"))
    company_name = _row_company_name(row)
    trace: list[dict[str, Any]] = []

    def attempt(method: str, args: dict[str, Any]) -> dict[str, Any] | None:
        firmo, err = client.call_tool_safe("company_firmographic", args)
        found = bool(firmo and firmo.get("found"))
        trace.append(
            {
                "method": method,
                "args": args,
                "found": found,
                "error": err,
            }
        )
        if err or not found:
            return None
        return firmo

    def success(
        firmo: dict[str, Any],
        *,
        method: str,
        resolved_domain: str,
        resolved_hg_id: str | None,
    ) -> dict[str, Any]:
        return {
            "found": True,
            "firmographic": firmo,
            "search_domain": search_domain,
            "canonical_domain": resolved_domain,
            "hg_id": resolved_hg_id,
            "company_name": firmo.get("name") or firmo.get("companyName") or company_name,
            "resolution_method": method,
            "resolution_trace": trace,
        }

    if hg_id:
        firmo = attempt("hg_id", {"hg_id": hg_id})
        if firmo:
            canonical = resolve_canonical_domain(firmo, search_domain)
            return success(
                firmo,
                method="hg_id",
                resolved_domain=canonical,
                resolved_hg_id=_firmographic_hg_id(firmo, hg_id),
            )

    if search_domain:
        firmo = attempt("search_domain", {"companyDomain": search_domain})
        if firmo:
            canonical = resolve_canonical_domain(firmo, search_domain)
            if canonical and canonical != search_domain:
                firmo_canonical = attempt("canonical_domain", {"companyDomain": canonical})
                if firmo_canonical:
                    return success(
                        firmo_canonical,
                        method="canonical_domain",
                        resolved_domain=canonical,
                        resolved_hg_id=_firmographic_hg_id(firmo_canonical, hg_id),
                    )
            return success(
                firmo,
                method="search_domain",
                resolved_domain=canonical or search_domain,
                resolved_hg_id=_firmographic_hg_id(firmo, hg_id),
            )

    if company_name:
        search, err = client.call_tool_safe(
            "search_companies",
            {"companyName": company_name, "limit": 25},
        )
        trace.append(
            {
                "method": "search_companies_by_name",
                "args": {"companyName": company_name, "limit": 25},
                "found": bool(search and (search.get("companies") or [])),
                "error": err,
            }
        )
        companies = (search or {}).get("companies") or []
        best = pick_best_search_company(company_name, companies)
        if best:
            name_domain = (best.get("domain") or best.get("companyDomain") or "").lower().strip()
            if name_domain:
                firmo = attempt("search_by_name", {"companyDomain": name_domain})
                if firmo:
                    canonical = resolve_canonical_domain(firmo, name_domain)
                    if canonical and canonical != name_domain:
                        firmo_canonical = attempt(
                            "canonical_domain_after_name",
                            {"companyDomain": canonical},
                        )
                        if firmo_canonical:
                            return success(
                                firmo_canonical,
                                method="canonical_domain_after_name",
                                resolved_domain=canonical,
                                resolved_hg_id=_firmographic_hg_id(firmo_canonical, hg_id),
                            )
                    return success(
                        firmo,
                        method="search_by_name",
                        resolved_domain=canonical or name_domain,
                        resolved_hg_id=_firmographic_hg_id(firmo, hg_id),
                    )

    return {
        "found": False,
        "reason": "firmographic_miss: all resolution attempts failed",
        "search_domain": search_domain,
        "company_name": company_name,
        "resolution_trace": trace,
    }


def preflight_firmographic(
    client: HgMcpClient,
    row: dict[str, Any],
) -> dict[str, Any]:
    """
    Ensure HG can score a prospect. Uses resolve_prospect_firmographic fallback chain.
    """
    resolved = resolve_prospect_firmographic(client, row)
    if not resolved.get("found"):
        return {
            "scorable": False,
            "reason": resolved.get("reason", "firmographic_miss"),
            "search_domain": resolved.get("search_domain"),
            "resolution_trace": resolved.get("resolution_trace"),
        }

    firmo = resolved["firmographic"]
    search_domain = resolved.get("search_domain") or ""
    canonical = resolved.get("canonical_domain") or search_domain
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
            "resolution_method": resolved.get("resolution_method"),
            "resolution_trace": resolved.get("resolution_trace"),
        }

    return {
        "scorable": True,
        "search_domain": search_domain,
        "canonical_domain": canonical,
        "hg_id": resolved.get("hg_id"),
        "firmographic": firmo,
        "revenue_usd": rev_f,
        "employee_count": emp_i,
        "it_spend_usd": float(it_spend) if it_spend else None,
        "company_name": resolved.get("company_name"),
        "resolution_method": resolved.get("resolution_method"),
        "resolution_trace": resolved.get("resolution_trace"),
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
                {
                    "domain": row.get("domain"),
                    "reason": pf.get("reason"),
                    "resolution_trace": pf.get("resolution_trace"),
                }
            )
            stats["preflight_trace"].append(
                {
                    "sample_position": row.get("sample_position"),
                    "domain": domain,
                    "company_name": row.get("companyName") or row.get("company_name"),
                    "outcome": "preflight_failed",
                    "reason": pf.get("reason"),
                    "resolution_trace": pf.get("resolution_trace"),
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
                "resolution_method": pf.get("resolution_method"),
            }
        )

    return selected, stats
