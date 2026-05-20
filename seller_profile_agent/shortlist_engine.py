"""Prospect universe search and deterministic ICP candidate filtering."""

from __future__ import annotations

import random
import re
from datetime import datetime, timezone
from typing import Any

from hg_client import HgMcpClient
from methodology_binding import MAX_SEARCH_LIMIT
from prospect_preflight import normalize_hg_id
from prospect_scorer import _company_args, _pick_total_it_spend

DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9-]{1,63}$")


def _normalize_domain(raw: str) -> str:
    text = (raw or "").strip().lower()
    text = text.replace("https://", "").replace("http://", "").split("/")[0]
    if text.startswith("www."):
        text = text[4:]
    return text.strip(".")


def _domain_hygiene_reason(domain: str) -> str | None:
    """Return reason when domain is too low-quality for reliable deep PRS calls."""
    if not domain:
        return "missing_domain"
    if "." not in domain:
        return "domain_without_tld"
    if "_" in domain or " " in domain:
        return "invalid_domain_characters"
    labels = domain.split(".")
    if len(labels) < 2:
        return "domain_without_tld"
    tld = labels[-1]
    if not tld.isalpha() or len(tld) < 2 or len(tld) > 24:
        return "invalid_tld"
    for label in labels:
        if not label:
            return "empty_domain_label"
        if label.startswith("-") or label.endswith("-"):
            return "invalid_domain_hyphen_position"
        if not DOMAIN_LABEL_RE.match(label):
            return "invalid_domain_label"
    return None


def _icp_values(seller: dict[str, Any]) -> dict[str, Any]:
    icp = seller.get("ideal_customer_profile") or {}
    out: dict[str, Any] = {
        "min_revenue": 50_000_000,
        "min_employees": 200,
        "min_it_spend": 2_000_000,
        "category": None,
    }
    for f in icp.get("filters") or []:
        fid = f.get("filter_id")
        if fid == "min_revenue_usd":
            out["min_revenue"] = f.get("value", out["min_revenue"])
        elif fid == "min_employees":
            out["min_employees"] = f.get("value", out["min_employees"])
        elif fid == "min_it_spend_usd":
            out["min_it_spend"] = f.get("value", out["min_it_spend"])
        elif fid == "category_adjacency_search":
            out["category"] = f.get("value")
    binding = (seller.get("selected_product") or {}).get("hg_binding") or {}
    if binding.get("hg_category_name"):
        out["category"] = binding["hg_category_name"]
    return out


def _seller_domain(seller: dict[str, Any]) -> str:
    raw = seller.get("raw_hg_data_used") or {}
    return (raw.get("resolved_domain") or "").lower().strip()


def build_search_arguments(
    seller: dict[str, Any],
    limit: int = MAX_SEARCH_LIMIT,
) -> dict[str, Any]:
    icp = _icp_values(seller)
    company = seller.get("company_name") or "seller"
    product = (seller.get("selected_product") or {}).get("product_name") or ""
    cap = min(max(1, limit), MAX_SEARCH_LIMIT)
    args: dict[str, Any] = {
        "searchCriteria": (
            f"Prospect pool for {company} — product line {product} — "
            f"revenue >= {icp['min_revenue']}, employees >= {icp['min_employees']} — "
            "land motion (seller SKU excluded)"
        ),
        "revenueMin": icp["min_revenue"],
        "employeesMin": icp["min_employees"],
        "limit": cap,
    }
    binding = (seller.get("selected_product") or {}).get("hg_binding") or {}
    exclude_name = binding.get("hg_product_name")
    if exclude_name:
        args["excludeTechnologies"] = [exclude_name]
    tech_terms: list[str] = []
    if icp.get("category"):
        tech_terms.append(icp["category"])
    if tech_terms:
        args["technologies"] = tech_terms[:3]
        args["technologyMode"] = "OR"
    return args


def fetch_prospect_universe(
    client: HgMcpClient,
    seller: dict[str, Any],
    limit: int = MAX_SEARCH_LIMIT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One search_companies call (fallback without technologies if needed)."""
    args = build_search_arguments(seller, limit=limit)
    meta: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "queries_attempted": [],
    }

    data, err = client.call_tool_safe("search_companies", args)
    meta["queries_attempted"].append({"args": dict(args), "error": err})

    companies = (data or {}).get("companies") or []
    if not companies and args.get("technologies"):
        fallback = {k: v for k, v in args.items() if k != "technologies"}
        fallback.pop("technologyMode", None)
        fallback["searchCriteria"] = (
            f"Prospect pool (fallback) — revenue >= {args.get('revenueMin')}, "
            f"employees >= {args.get('employeesMin')}"
        )
        data, err = client.call_tool_safe("search_companies", fallback)
        meta["queries_attempted"].append({"args": fallback, "error": err})
        companies = (data or {}).get("companies") or []

    meta["count"] = len(companies)
    meta["search_metadata"] = (data or {}).get("metadata")
    return companies, meta


def _row_label(row: dict[str, Any]) -> str:
    return (
        row.get("companyName")
        or row.get("company_name")
        or row.get("domain")
        or row.get("companyDomain")
        or "?"
    )


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _passes_floor(value: float | int | None, floor: float | int) -> bool | None:
    if value is None:
        return None
    return value >= floor


def build_icp_candidate_list(
    companies: list[dict[str, Any]],
    seller: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Hygiene + deterministic ICP gates only. No scoring, weighting, ranking, or sorting.
    Returns every ICP-compatible account in the original HG search order.
    """
    icp = _icp_values(seller)
    seller_dom = _seller_domain(seller)
    min_rev = float(icp["min_revenue"])
    min_emp = int(icp["min_employees"])
    min_it_spend = float(icp["min_it_spend"])

    stats: dict[str, Any] = {
        "input_count": len(companies),
        "after_hygiene": 0,
        "candidate_count": 0,
        "hygiene": {
            "function": "shortlist_engine.build_icp_candidate_list",
            "criteria": [
                "domain is present",
                "domain format is valid (host + TLD + RFC-like labels)",
                "domain is unique after lowercasing",
                "domain is not the seller domain",
            ],
            "removed_missing_domain": 0,
            "removed_invalid_domain": 0,
            "removed_duplicate_domain": 0,
            "removed_seller_domain": 0,
            "removed_missing_domain_rows": [],
            "removed_invalid_domain_rows": [],
            "removed_duplicate_domain_rows": [],
            "removed_seller_domain_rows": [],
        },
        "icp_thresholds": {
            "min_revenue": min_rev,
            "min_employees": min_emp,
            "min_it_spend": min_it_spend,
            "category": icp.get("category"),
        },
        "eliminated_by_threshold": [],
        "retained_with_unknown_fields": [],
        "selection_policy": "deterministic_icp_filter_only_no_scoring_no_ranking",
    }

    seen_domains: dict[str, str] = {}
    cleaned: list[dict[str, Any]] = []
    for row in companies:
        raw_domain = row.get("domain") or row.get("companyDomain") or ""
        domain = _normalize_domain(raw_domain)
        if not domain:
            stats["hygiene"]["removed_missing_domain"] += 1
            stats["hygiene"]["removed_missing_domain_rows"].append(
                {
                    "company_name": _row_label(row),
                    "raw_domain": raw_domain,
                    "country": row.get("country"),
                    "industry": row.get("industry"),
                    "reason": "HG search returned no usable domain/companyDomain.",
                }
            )
            continue
        bad_reason = _domain_hygiene_reason(domain)
        if bad_reason:
            stats["hygiene"]["removed_invalid_domain"] += 1
            stats["hygiene"]["removed_invalid_domain_rows"].append(
                {
                    "company_name": _row_label(row),
                    "raw_domain": raw_domain,
                    "normalized_domain": domain,
                    "country": row.get("country"),
                    "industry": row.get("industry"),
                    "reason": f"Domain rejected by hygiene: {bad_reason}.",
                }
            )
            continue
        if domain in seen_domains:
            stats["hygiene"]["removed_duplicate_domain"] += 1
            stats["hygiene"]["removed_duplicate_domain_rows"].append(
                {
                    "company_name": _row_label(row),
                    "domain": domain,
                    "kept_company_name": seen_domains[domain],
                    "country": row.get("country"),
                    "industry": row.get("industry"),
                    "reason": "Duplicate normalized domain; first occurrence was kept.",
                }
            )
            continue
        if seller_dom and domain == seller_dom:
            stats["hygiene"]["removed_seller_domain"] += 1
            stats["hygiene"]["removed_seller_domain_rows"].append(
                {
                    "company_name": _row_label(row),
                    "domain": domain,
                    "country": row.get("country"),
                    "industry": row.get("industry"),
                    "reason": "Same domain as seller; removed to avoid scoring the seller.",
                }
            )
            continue
        seen_domains[domain] = _row_label(row)
        cleaned.append(row)

    stats["after_hygiene"] = len(cleaned)
    stats["hygiene"]["kept_after_hygiene"] = len(cleaned)

    eligible: list[dict[str, Any]] = []
    for row in cleaned:
        rev = _to_float(row.get("revenueAmount") or row.get("revenue"))
        emp = _to_int(row.get("employeeCount") or row.get("employees"))
        it_spend = _to_float(row.get("itSpend") or row.get("it_spend"))
        flags: list[str] = []

        rev_ok = _passes_floor(rev, min_rev)
        emp_ok = _passes_floor(emp, min_emp)
        it_ok = _passes_floor(it_spend, min_it_spend)

        failed: list[str] = []
        if rev_ok is False:
            failed.append("revenue")
        if emp_ok is False:
            failed.append("employees")
        if it_ok is False:
            failed.append("it_spend")

        if failed:
            stats["eliminated_by_threshold"].append(
                {
                    "company_name": _row_label(row),
                    "domain": row.get("domain") or row.get("companyDomain"),
                    "revenue": rev,
                    "employees": emp,
                    "it_spend": it_spend,
                    "failed_filters": failed,
                    "reason": f"Below deterministic ICP floor(s): {', '.join(failed)}",
                }
            )
            continue

        if rev_ok is None:
            flags.append("revenue_unknown_in_search")
        if emp_ok is None:
            flags.append("employees_unknown_in_search")
        if it_ok is None:
            flags.append("it_spend_unknown_in_search")

        if flags:
            stats["retained_with_unknown_fields"].append(
                {
                    "company_name": _row_label(row),
                    "domain": row.get("domain") or row.get("companyDomain"),
                    "unknown_fields": flags,
                }
            )

        eligible.append(
            {
                **row,
                "_flags": flags,
                "icp_status": "passed",
                "icp_pass_reason": (
                    "Passed deterministic search/filter constraints; no score or rank assigned."
                )
            }
        )

    stats["candidate_count"] = len(eligible)
    stats["after_hard_filter"] = len(eligible)
    return eligible, stats


def enrich_candidates_it_spend(
    client: HgMcpClient,
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Fetch Total IT spend (or firmographic IT spend) for candidate audit tables.
    search_companies rows usually omit itSpend; this fills values via MCP per domain.
    """
    meta: dict[str, Any] = {
        "enriched_count": 0,
        "from_company_spend": 0,
        "from_firmographic": 0,
        "still_missing": 0,
        "skipped_no_domain": 0,
    }
    enriched: list[dict[str, Any]] = []

    for row in candidates:
        copy = dict(row)
        domain = (copy.get("domain") or copy.get("companyDomain") or "").strip()
        if not domain:
            meta["skipped_no_domain"] += 1
            enriched.append(copy)
            continue

        existing = _to_float(copy.get("itSpend") or copy.get("it_spend"))
        if existing is not None:
            meta["enriched_count"] += 1
            enriched.append(copy)
            continue

        hg_id = normalize_hg_id(copy.get("companyId") or copy.get("hgId"))
        args = _company_args(domain, hg_id)

        spend_payload, spend_err = client.call_tool_safe("company_spend", args)
        if not spend_err and spend_payload:
            it_val, _ = _pick_total_it_spend(spend_payload)
            if it_val is not None:
                copy["itSpend"] = it_val
                copy["_icp_it_spend_source"] = "company_spend.totalSpendAmount"
                meta["enriched_count"] += 1
                meta["from_company_spend"] += 1
                enriched.append(copy)
                continue

        firmo, firmo_err = client.call_tool_safe("company_firmographic", args)
        if not firmo_err and firmo and firmo.get("found"):
            it_raw = firmo.get("itSpend") or firmo.get("it_spend")
            it_val = _to_float(it_raw)
            if it_val is not None:
                copy["itSpend"] = it_val
                copy["_icp_it_spend_source"] = "company_firmographic.itSpend"
                meta["enriched_count"] += 1
                meta["from_firmographic"] += 1
                enriched.append(copy)
                continue

        meta["still_missing"] += 1
        enriched.append(copy)

    return enriched, meta


def sample_icp_candidates(
    candidates: list[dict[str, Any]],
    count: int,
    seed: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Randomly sample ICP-compatible companies before any PRS scoring."""
    sample_size = max(0, min(count, len(candidates)))
    rng = random.Random(seed) if seed is not None else random.SystemRandom()
    picked = rng.sample(candidates, sample_size) if sample_size else []
    sampled = [
        {
            **row,
            "sample_position": idx,
            "sample_status": "selected_for_deep_prs",
        }
        for idx, row in enumerate(picked, start=1)
    ]
    return sampled, {
        "sample_method": "uniform_random_without_replacement",
        "sample_seed": seed,
        "requested_count": count,
        "sampled_count": len(sampled),
        "candidate_count": len(candidates),
        "sample_fraction": (len(sampled) / len(candidates)) if candidates else 0,
    }
