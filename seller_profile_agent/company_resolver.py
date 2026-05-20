"""Resolve a user-entered company name to HG firmographic record."""

from __future__ import annotations

import re
from typing import Any

from hg_client import HgMcpClient

# Demo-friendly domain hints (still verified via company_firmographic).
KNOWN_DOMAINS: dict[str, str] = {
    "amazon": "amazon.com",
    "microsoft": "microsoft.com",
    "google": "google.com",
    "airbnb": "airbnb.com",
    "salesforce": "salesforce.com",
    "oracle": "oracle.com",
    "ibm": "ibm.com",
    "apple": "apple.com",
    "meta": "meta.com",
    "facebook": "meta.com",
    "netflix": "netflix.com",
    "uber": "uber.com",
    "stripe": "stripe.com",
    "doordash": "doordash.com",
    "databricks": "databricks.com",
}

# Common typos → canonical slug used for domain / KNOWN_DOMAINS lookup.
TYPO_ALIASES: dict[str, str] = {
    "databrics": "databricks",
    "data bricks": "databricks",
    "data-bricks": "databricks",
}


def _apply_typo_alias(company_input: str) -> str | None:
    """Return corrected input if a known typo was entered, else None."""
    raw = company_input.strip().lower()
    slug = _normalize_name(company_input)
    if raw in TYPO_ALIASES:
        return TYPO_ALIASES[raw]
    if slug in TYPO_ALIASES:
        return TYPO_ALIASES[slug]
    return None


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _domain_candidates(company_input: str) -> list[str]:
    raw = company_input.strip().lower()
    candidates: list[str] = []
    if raw in KNOWN_DOMAINS:
        candidates.append(KNOWN_DOMAINS[raw])
    if "." in raw and " " not in raw:
        candidates.append(raw)
    slug = _normalize_name(company_input)
    if slug:
        candidates.append(f"{slug}.com")
    # de-dupe preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for domain in candidates:
        if domain not in seen:
            seen.add(domain)
            ordered.append(domain)
    return ordered


def _score_search_hit(query: str, company: dict[str, Any]) -> int:
    q = _normalize_name(query)
    name = _normalize_name(company.get("companyName", ""))
    domain = (company.get("domain") or "").lower()
    score = 0
    if name == q:
        score += 100
    if q and q in name:
        score += 40
    if domain.startswith(q) or q in _normalize_name(domain.split(".")[0]):
        score += 30
    if company.get("revenueAmount", -1) not in (-1, None) and company.get("revenueAmount", 0) > 0:
        score += 5
    if company.get("employeeCount", -1) not in (-1, None) and company.get("employeeCount", 0) > 0:
        score += 5
    return score


def resolve_company(client: HgMcpClient, company_input: str) -> dict[str, Any] | None:
    """Return firmographic payload with found=True, or None."""
    queries: list[str] = [company_input.strip()]
    alias = _apply_typo_alias(company_input)
    if alias and alias not in queries:
        queries.append(alias)

    for query in queries:
        for domain in _domain_candidates(query):
            firmo = client.call_tool("company_firmographic", {"companyDomain": domain})
            if firmo.get("found"):
                firmo["_resolved_domain"] = domain
                if query != company_input.strip():
                    firmo["_input_corrected_from"] = company_input.strip()
                    firmo["_input_corrected_to"] = query
                return firmo

        search = client.call_tool(
            "search_companies",
            {"companyName": query, "limit": 25},
        )
        companies = search.get("companies") or []
        if not companies:
            continue

        ranked = sorted(
            companies,
            key=lambda c: _score_search_hit(query, c),
            reverse=True,
        )
        best = ranked[0]
        domain = best.get("domain")
        if not domain:
            continue

        firmo = client.call_tool("company_firmographic", {"companyDomain": domain})
        if firmo.get("found"):
            firmo["_resolved_domain"] = domain
            firmo["_search_match"] = best
            if query != company_input.strip():
                firmo["_input_corrected_from"] = company_input.strip()
                firmo["_input_corrected_to"] = query
            return firmo
    return None


def resolution_hint(company_input: str) -> str:
    """Human-readable hint when resolve_company returns None."""
    domains = _domain_candidates(company_input)
    alias = _apply_typo_alias(company_input)
    lines = [
        f"Tried domains: {', '.join(domains)}",
        f"HG search by name: {company_input.strip()!r}",
    ]
    if alias:
        lines.append(
            f"Did you mean {alias!r}? Try: npm run profile:seller  (or company: {alias}) "
            f"— HG resolves {KNOWN_DOMAINS.get(alias, alias + '.com')}."
        )
    else:
        lines.append(
            "Tip: use the official domain (e.g. databricks.com) if the name is ambiguous."
        )
    return " | ".join(lines)


def format_revenue_range(revenue: Any) -> str | None:
    if revenue is None:
        return None
    try:
        value = float(revenue)
    except (TypeError, ValueError):
        return str(revenue) if revenue else None
    if value <= 0:
        return None
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B+"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M+"
    return f"${value:,.0f}"


def format_employee_range(employees: Any) -> str | None:
    if employees is None:
        return None
    try:
        count = int(employees)
    except (TypeError, ValueError):
        return str(employees) if employees else None
    if count <= 0:
        return None
    return f"{count:,} employees"
