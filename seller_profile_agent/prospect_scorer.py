"""Fetch prospect HG data and run PRS scoring."""

from __future__ import annotations

import random
from typing import Any

from hg_client import HgMcpClient, HgMcpError
from prs_criteria import CRITERION_META, display_name
from prs_engine import (
    CriterionResult,
    ProspectScore,
    aggregate_prs,
    score_achat,
    score_besoin,
    score_budget,
    score_dynamique,
    score_taille,
)
from hg_value_parser import extract_firmographic_size, parse_hg_numeric
from prospect_preflight import is_search_range_proxy, normalize_hg_id


def _company_args(domain: str, hg_id: str | None) -> dict[str, Any]:
    if hg_id:
        return {"hg_id": hg_id}
    return {"companyDomain": domain}


def _fetch_firmographic_with_fallback(
    client: HgMcpClient,
    *,
    domain: str,
    hg_id: str | None,
) -> tuple[dict[str, Any] | None, str | None, str]:
    """
    Resolve firmographics robustly.

    HG rows can have fragile identifiers (or domains that don't resolve). We try both
    key types before failing so deep PRS can proceed whenever one identifier works.
    """
    attempts: list[tuple[str, dict[str, Any]]] = []
    if hg_id:
        attempts.append(("hg_id", {"hg_id": hg_id}))
    if domain:
        attempts.append(("companyDomain", {"companyDomain": domain}))
    if hg_id and domain:
        # Try reverse order as last resort for inconsistent records.
        attempts.append(("companyDomain_fallback", {"companyDomain": domain}))
        attempts.append(("hg_id_fallback", {"hg_id": hg_id}))

    seen_args: set[str] = set()
    tried: list[str] = []
    for label, args in attempts:
        key = str(sorted(args.items()))
        if key in seen_args:
            continue
        seen_args.add(key)
        tried.append(f"{label}={args}")
        payload, err = client.call_tool_safe("company_firmographic", args)
        if err:
            continue
        if payload and payload.get("found"):
            return payload, None, "; ".join(tried)
    return None, "not_found_or_unresolvable", "; ".join(tried)


def _pick_total_it_spend(spend_payload: dict[str, Any]) -> tuple[float | None, Any]:
    rows = spend_payload.get("spendByCategory") or spend_payload.get("categories") or []
    unknown = spend_payload.get("unknownRowCount")
    for row in rows:
        name = (row.get("categoryName") or row.get("name") or "").lower()
        if "total it" in name or name == "total it":
            amount = row.get("totalSpendAmount") or row.get("totalSpend")
            try:
                return float(amount), unknown
            except (TypeError, ValueError):
                pass
    for key in ("totalSpendAmount", "totalItSpend", "total_spend"):
        if spend_payload.get(key):
            try:
                return float(spend_payload[key]), unknown
            except (TypeError, ValueError):
                pass
    return None, unknown


def _attach_meta(crit: CriterionResult, explanation: str) -> CriterionResult:
    crit.inputs["display_name"] = display_name(crit.criterion_id)
    crit.inputs["explanation"] = explanation
    return crit


def _max_category_intensity(tech_payload: dict[str, Any], category_name: str | None) -> float | None:
    if not category_name:
        return None
    cat_low = category_name.lower()
    products = tech_payload.get("products") or []
    intensities: list[float] = []
    for item in products:
        trees = item.get("categoryNameTrees") or item.get("categories") or []
        names: list[str] = []
        for t in trees:
            if isinstance(t, str):
                names.append(t.lower())
            elif isinstance(t, dict):
                names.append((t.get("name") or "").lower())
        cat_field = (item.get("categoryName") or "").lower()
        if cat_field:
            names.append(cat_field)
        attrs = item.get("productAttributes") or []
        for a in attrs:
            if isinstance(a, str):
                names.append(a.lower())
        if any(cat_low in n or n in cat_low for n in names):
            try:
                intensities.append(float(item.get("intensity") or 0))
            except (TypeError, ValueError):
                pass
    return max(intensities) if intensities else None


def _extract_intent_topic(
    intent_payload: dict[str, Any], topic_names: list[str]
) -> tuple[float | None, str | None, str | None, str | None]:
    topics = intent_payload.get("topics") or []
    end_date = (intent_payload.get("window") or {}).get("end")
    candidates = [t for t in topic_names if t]
    for topic in topics:
        name = topic.get("topic_name") or topic.get("topicName") or ""
        for wanted in candidates:
            if wanted.lower() in name.lower() or name.lower() in wanted.lower():
                return topic.get("score"), topic.get("last_seen_at"), end_date, name
    return None, None, end_date, None


def _extract_momentum(series_payload: dict[str, Any], product_name: str | None) -> tuple[Any, bool]:
    products = series_payload.get("products") or []
    if not products:
        return None, False
    pname = (product_name or "").lower()
    for item in products:
        name = (item.get("productName") or item.get("name") or "").lower()
        if pname and (pname in name or name in pname):
            return item.get("intensity_momentum"), True
    return None, False


def fetch_random_prospects(
    client: HgMcpClient,
    count: int,
    seed_query: str = "technology",
) -> list[dict[str, Any]]:
    """Legacy random pool (prefer pipeline ICP filtering + sampling for production runs)."""
    data, err = client.call_tool_safe(
        "search_companies",
        {
            "searchCriteria": f"Random prospect pool for PRS demo ({seed_query})",
            "employeesMin": 500,
            "limit": max(count * 8, 40),
        },
    )
    if err or not data:
        data, _ = client.call_tool_safe(
            "search_companies",
            {"searchCriteria": seed_query, "limit": max(count * 8, 40)},
        )
    companies = (data or {}).get("companies") or []
    random.shuffle(companies)
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for company in companies:
        domain = (company.get("domain") or company.get("companyDomain") or "").lower().strip()
        if not domain or domain in seen:
            continue
        seen.add(domain)
        picked.append(company)
        if len(picked) >= count:
            break
    return picked


def score_prospect(
    client: HgMcpClient,
    company: dict[str, Any],
    binding: dict[str, Any],
) -> ProspectScore:
    search_domain = (company.get("domain") or company.get("companyDomain") or "").lower().strip()
    preflight = company.get("_preflight") or {}
    hg_id = normalize_hg_id(preflight.get("hg_id")) or normalize_hg_id(company.get("companyId"))
    domain = (preflight.get("canonical_domain") or search_domain).lower().strip()

    company_name = (
        preflight.get("company_name")
        or company.get("companyName")
        or company.get("name")
        or domain
    )
    notes: list[str] = []
    mcp_evidence: dict[str, Any] = {"search_domain": search_domain, "canonical_domain": domain}

    product_id = binding.get("hg_product_id")
    product_name = binding.get("hg_product_name") or binding.get("hg_intent_topic_name")
    intent_name = binding.get("hg_intent_topic_name") or product_name
    category_name = binding.get("hg_category_name")

    base_args = _company_args(domain, hg_id)

    firmo = preflight.get("firmographic")
    if not firmo:
        firmo, ferr, tried = _fetch_firmographic_with_fallback(
            client,
            domain=domain,
            hg_id=hg_id,
        )
        if not firmo:
            raise HgMcpError(
                f"Firmographic required but failed for {domain}: {ferr}; tried {tried}"
            )
    mcp_evidence["firmographic"] = {"found": True, "domain": domain}

    revenue_raw = firmo.get("revenue") or firmo.get("revenueAmount")
    employees_raw = firmo.get("employeeCount") or firmo.get("employees")
    revenue, employees = extract_firmographic_size(firmo, company)
    if is_search_range_proxy(
        company.get("revenueAmount"),
        company.get("employeeCount"),
        company.get("employeesRange"),
    ):
        notes.append(
            "Search row uses HG bucket floors; size metrics prefer parsed firmographic values."
        )

    c_taille = score_taille(revenue, employees)
    c_taille.inputs.update(
        {
            "revenue_usd": revenue,
            "employee_count": employees,
            "revenue_raw": revenue_raw,
            "employees_raw": employees_raw,
            "data_source": "company_firmographic",
        }
    )
    _attach_meta(
        c_taille,
        f"Account scale from HG revenue/headcount (rev={revenue}, emp={employees}).",
    )

    it_budget = parse_hg_numeric(firmo.get("itSpend") or firmo.get("it_spend"))
    unknown_rows = None
    spend, err = client.call_tool_safe("company_spend", {**base_args, "limit": 50})
    if err:
        notes.append(f"company_spend: {err}")
        mcp_evidence["company_spend"] = {"error": err}
    elif spend:
        spend_it, unknown_rows = _pick_total_it_spend(spend)
        mcp_evidence["company_spend"] = {"total_it": spend_it, "unknownRowCount": unknown_rows}
        if spend_it:
            it_budget = spend_it
    c_budget = score_budget(it_budget, unknown_rows)
    c_budget.inputs.update(
        {
            "it_budget_usd": it_budget,
            "unknown_row_count": unknown_rows,
            "data_source": "company_spend" if spend and not err else "company_firmographic",
        }
    )
    _attach_meta(
        c_budget,
        "IT budget from Total IT spend line when available; drives funding capacity.",
    )

    tech_all: dict[str, Any] = {}
    tech_args: dict[str, Any] = {**base_args, "maxResults": 150}

    tech_payload, err = client.call_tool_safe("company_technographic", tech_args)
    if err:
        notes.append(f"company_technographic: {err}")
        mcp_evidence["company_technographic"] = {"error": err}
    elif tech_payload:
        tech_all = tech_payload
        mcp_evidence["company_technographic"] = {
            "product_count": len(tech_all.get("products") or []),
        }

    intensity_max = _max_category_intensity(tech_all, category_name) if tech_all else None
    c_besoin = score_besoin(intensity_max, category_name)
    c_besoin.inputs.update(
        {
            "category_name": category_name,
            "max_category_intensity": intensity_max,
        }
    )
    _attach_meta(
        c_besoin,
        f"Max HG intensity in '{category_name}' category among installed products.",
    )

    topic_score, last_seen, end_date, matched_topic = None, None, None, None
    intent_queries = [intent_name, product_name, binding.get("hg_intent_topic_name")]
    for q in intent_queries:
        if not q:
            continue
        intent, ierr = client.call_tool_safe(
            "company_intent",
            {**base_args, "product_name": q, "limit": 50},
        )
        if ierr:
            notes.append(f"company_intent({q}): {ierr}")
            continue
        if intent:
            topic_score, last_seen, end_date, matched_topic = _extract_intent_topic(
                intent, [q, product_name or "", intent_name or ""]
            )
            mcp_evidence["company_intent"] = {
                "query": q,
                "matched_topic": matched_topic,
                "score": topic_score,
            }
            if topic_score is not None:
                break

    c_achat = score_achat(topic_score, last_seen, end_date)
    c_achat.inputs.update(
        {
            "intent_topic": matched_topic or intent_name,
            "intent_score": topic_score,
            "last_seen_at": last_seen,
        }
    )
    _attach_meta(c_achat, "Purchase intent from HG topic score with freshness tiers.")

    momentum, found = None, False
    series_product = product_name
    if product_id:
        series, serr = client.call_tool_safe(
            "company_install_time_series",
            {
                **base_args,
                "timeRange": "last_24_months",
                "products": [product_id],
            },
        )
        if not serr and series:
            momentum, found = _extract_momentum(series, product_name)
            mcp_evidence["company_install_time_series"] = {
                "products": [product_id],
                "momentum": momentum,
                "found": found,
            }
    if not found and product_name:
        series, serr = client.call_tool_safe(
            "company_install_time_series",
            {
                **base_args,
                "timeRange": "last_24_months",
                "products": [product_name],
            },
        )
        if serr:
            notes.append(f"company_install_time_series: {serr}")
        elif series:
            momentum, found = _extract_momentum(series, product_name)
            mcp_evidence["company_install_time_series"] = {
                "products": [series_product],
                "momentum": momentum,
                "found": found,
            }

    c_dynamique = score_dynamique(momentum, found)
    c_dynamique.inputs.update(
        {"intensity_momentum": momentum, "time_series_found": found}
    )
    _attach_meta(
        c_dynamique,
        "HG intensity_momentum on the bound seller SKU (24 months): rising, flat, or declining.",
    )

    criteria = {
        "taille": c_taille,
        "budget": c_budget,
        "besoin": c_besoin,
        "achat": c_achat,
        "dynamique": c_dynamique,
    }

    prs, r_global, prs_steps = aggregate_prs(criteria)

    result = ProspectScore(
        company_name=company_name,
        domain=domain,
        prs=prs,
        reliability_global=r_global,
        criteria=criteria,
        raw_notes=notes,
    )
    result.criteria["_aggregate"] = CriterionResult(
        criterion_id="_aggregate",
        score=prs,
        reliability=r_global,
        weight=1.0,
        contribution=prs,
        included_in_prs=True,
        calculation_steps=prs_steps + ([f"Note: {n}" for n in notes] if notes else []),
        inputs={"mcp_evidence": mcp_evidence},
    )
    return result
