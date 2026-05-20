"""Resolve PRS methodology fields from seller profile + HG MCP catalog."""

from __future__ import annotations

import re
from typing import Any

from hg_client import HgMcpClient, HgMcpError
from product_discovery import EXTRA_VENDORS, _fetch_vendor_products

# PRS weights from la-methodologie.md
PRS_WEIGHTS = {
    "taille": 0.25,
    "budget": 0.20,
    "besoin": 0.20,
    "achat": 0.20,
    "dynamique": 0.15,
}

MAX_SEARCH_LIMIT = 165

# Prospect-side MCP features required per criterion (methodology checklist).
PRS_CRITERIA_SPEC = [
    {
        "criterion_id": "taille",
        "criterion_name": "Account size",
        "weight": 0.25,
        "prospect_mcp_tools": ["company_firmographic"],
        "prospect_fields": ["revenue", "employeeCount"],
        "seller_profile_fields": [],
        "formula": "S_taille = max(S_rev, S_emp)",
    },
    {
        "criterion_id": "budget",
        "criterion_name": "IT budget",
        "weight": 0.20,
        "prospect_mcp_tools": ["company_spend", "company_firmographic"],
        "prospect_fields": ["totalSpendAmount", "itSpend"],
        "seller_profile_fields": [],
        "formula": "S_budget = max(0, min(100, 100 * log10(IT_budget / 100000) / 4))",
    },
    {
        "criterion_id": "besoin",
        "criterion_name": "Category need intensity",
        "weight": 0.20,
        "prospect_mcp_tools": ["company_technographic"],
        "prospect_fields": ["intensity", "categories"],
        "seller_profile_fields": [
            "selected_product.hg_binding.hg_category_name",
            "selected_product.hg_binding.hg_category_id",
        ],
        "formula": "S_besoin = min(100, max intensity in target category)",
    },
    {
        "criterion_id": "achat",
        "criterion_name": "Purchase intent",
        "weight": 0.20,
        "prospect_mcp_tools": ["company_intent"],
        "prospect_fields": ["topics.score", "topics.last_seen_at"],
        "seller_profile_fields": [
            "selected_product.hg_binding.hg_intent_topic_name",
            "selected_product.hg_binding.hg_product_name",
        ],
        "formula": "S_achat = min(100, score * freshness_tier)",
    },
    {
        "criterion_id": "dynamique",
        "criterion_name": "Product adoption momentum",
        "weight": 0.15,
        "prospect_mcp_tools": ["company_install_time_series"],
        "prospect_fields": ["intensity_momentum"],
        "seller_profile_fields": [
            "selected_product.hg_binding.hg_product_id",
        ],
        "formula": "100 if intensity_momentum > 0; 50 if 0; 0 if < 0",
    },
]


def _parse_examples(reasoning: str) -> list[str]:
    match = re.search(r"Examples:\s*([^.]+)", reasoning, re.IGNORECASE)
    if not match:
        return []
    return [part.strip() for part in match.group(1).split(",") if part.strip()]


COMPETITOR_SOURCE_KEYS = {
    "competitors",
    "competitorProducts",
    "competitor_products",
    "competingProducts",
    "competing_products",
    "alternativeProducts",
    "alternative_products",
    "alternatives",
}


def _normalize_product_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _extract_product_identity(row: dict[str, Any]) -> tuple[str | None, str | None]:
    pid = (
        row.get("productId")
        or row.get("product_id")
        or row.get("id")
        or row.get("hg_product_id")
        or row.get("hgProductId")
    )
    pname = (
        row.get("productName")
        or row.get("product_name")
        or row.get("name")
        or row.get("title")
        or row.get("hg_product_name")
        or row.get("hgProductName")
    )
    return (str(pid) if pid else None, str(pname).strip() if pname else None)


def _iter_competitor_sources(payload: Any, path: str = "$") -> list[dict[str, Any]]:
    """
    Return candidate competitor arrays with their JSON path.

    This is intentionally conservative: only keys whose names explicitly mean competitor
    or alternative products are treated as source lists.
    """
    found: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{path}.{key}"
            if key in COMPETITOR_SOURCE_KEYS:
                rows = value if isinstance(value, list) else [value]
                found.append({"path": next_path, "source_key": key, "rows": rows})
            if isinstance(value, (dict, list)):
                found.extend(_iter_competitor_sources(value, next_path))
    elif isinstance(payload, list):
        for idx, item in enumerate(payload):
            if isinstance(item, (dict, list)):
                found.extend(_iter_competitor_sources(item, f"{path}[{idx}]"))
    return found


def _resolve_hg_competitors(
    client: HgMcpClient,
    product_name: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Closed list of competitor SKUs from HG catalog, with auditable extraction trace."""
    resolution: dict[str, Any] = {
        "method": "get_product_information(includeCompetitors=True)",
        "query_product_name": product_name,
        "accepted_source_keys": sorted(COMPETITOR_SOURCE_KEYS),
        "source_paths": [],
        "normalized_count": 0,
        "status": "not_run",
    }
    if not product_name:
        resolution["status"] = "skipped_missing_product_name"
        return [], resolution

    args = {"productName": product_name, "includeCompetitors": True}
    info, err = client.call_tool_safe("get_product_information", args)
    resolution["tool_args"] = args
    if err or not info:
        resolution["status"] = "tool_error" if err else "empty_response"
        resolution["error"] = err
        return [], resolution

    resolution["response_top_level_keys"] = sorted(info.keys()) if isinstance(info, dict) else []
    sources = _iter_competitor_sources(info)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    target_name = _normalize_product_name(product_name)

    for source in sources:
        extracted = 0
        for row in source["rows"]:
            if not isinstance(row, dict):
                continue
            pid, pname = _extract_product_identity(row)
            if not pid and not pname:
                continue
            if pname and _normalize_product_name(pname) == target_name:
                continue
            dedupe_key = f"id:{pid}" if pid else f"name:{_normalize_product_name(pname)}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            out.append(
                {
                    "product_id": pid,
                    "product_name": pname,
                    "source_path": source["path"],
                    "source_key": source["source_key"],
                }
            )
            extracted += 1
        resolution["source_paths"].append(
            {
                "path": source["path"],
                "source_key": source["source_key"],
                "rows_seen": len(source["rows"]),
                "rows_extracted": extracted,
            }
        )

    resolution["normalized_count"] = len(out)
    resolution["status"] = "resolved" if out else "no_competitor_products_in_accepted_fields"
    return out, resolution


def _name_score(candidate: str, keywords: list[str]) -> int:
    low = candidate.lower()
    score = 0
    for kw in keywords:
        k = kw.lower()
        if low == k:
            score += 100
        elif k in low or low in k:
            score += 40
        for token in k.split():
            if len(token) > 3 and token in low:
                score += 10
    return score


def _collect_vendor_catalog(
    client: HgMcpClient,
    company_name: str,
    domain: str,
    vendor_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    domain_root = (domain or "").split(".")[0].lower()
    slug = re.sub(r"[^a-z0-9]+", "", company_name.lower())
    vendor_names = EXTRA_VENDORS.get(domain_root) or EXTRA_VENDORS.get(slug) or [company_name]

    catalog: list[dict[str, Any]] = []
    for vendor_name in vendor_names:
        try:
            catalog.extend(_fetch_vendor_products(client, vendor_name))
        except HgMcpError:
            continue
    return catalog


def _pick_catalog_product(
    selected: dict[str, Any],
    catalog: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not catalog:
        return None

    selected_id = selected.get("hg_product_id")
    if selected_id:
        for product in catalog:
            if str(product.get("product_id") or "") == str(selected_id):
                return product

    selected_name = (selected.get("product_name") or "").strip()
    if selected_name:
        for product in catalog:
            if (product.get("product_name") or "").lower() == selected_name.lower():
                return product

    keywords = [selected.get("product_name", "")]
    examples = _parse_examples(selected.get("reasoning", ""))
    keywords.extend(examples)

    # Prefer exact HG catalog name from examples (e.g. "Amazon Redshift" over "Amazon Redshift Spectrum").
    for example in examples:
        for product in catalog:
            if (product.get("product_name") or "").lower() == example.lower():
                return product

    ranked = sorted(
        catalog,
        key=lambda p: _name_score((p.get("product_name") or ""), keywords),
        reverse=True,
    )
    best = ranked[0]
    if _name_score(best.get("product_name", ""), keywords) <= 0:
        return None
    return best


def _lookup_category(client: HgMcpClient, query: str) -> dict[str, Any] | None:
    try:
        data = client.call_tool("list_product_categories", {"query": query, "limit": 10})
    except HgMcpError:
        return None
    categories = data.get("categories") or []
    if not categories:
        return None
    ranked = sorted(
        categories,
        key=lambda c: _name_score(c.get("name", ""), [query]),
        reverse=True,
    )
    return ranked[0]


def _lookup_intent_topic(client: HgMcpClient, query: str) -> dict[str, Any] | None:
    try:
        data = client.call_tool("list_intent_topics", {"query": query, "limit": 10})
    except HgMcpError:
        return None
    topics = data.get("topics") or []
    if not topics:
        return None
    ranked = sorted(
        topics,
        key=lambda t: _name_score(t.get("name", ""), [query]),
        reverse=True,
    )
    return ranked[0]


def build_hg_product_binding(
    client: HgMcpClient,
    selected: dict[str, Any],
    company_name: str,
    domain: str,
    vendor_summary: dict[str, Any],
) -> dict[str, Any]:
    """Map selected sellable line to HG catalog product, category, and intent topic."""
    catalog = _collect_vendor_catalog(client, company_name, domain, vendor_summary)
    catalog_pick = _pick_catalog_product(selected, catalog)

    product_name = selected.get("product_name", "")
    examples = _parse_examples(selected.get("reasoning", ""))
    intent_query = catalog_pick.get("product_name") if catalog_pick else (examples[0] if examples else product_name)
    category_query = selected.get("product_category") or product_name

    category = _lookup_category(client, category_query)
    if not category and "data" in category_query.lower():
        category = _lookup_category(client, "database")
    if not category and "warehouse" in category_query.lower():
        category = _lookup_category(client, "data warehouse")
    if category and "warehouse" in category_query.lower():
        alt = _lookup_category(client, "database management")
        if alt and _name_score(alt.get("name", ""), ["database management", "data warehouse"]) >= _name_score(
            category.get("name", ""), ["database management", "data warehouse"]
        ):
            category = alt

    intent_queries = [intent_query]
    intent_queries.extend(examples)
    if catalog_pick and catalog_pick.get("product_name"):
        intent_queries.append(catalog_pick["product_name"])
    intent_queries.append(product_name)

    intent_topic = None
    seen_q: set[str] = set()
    for query in intent_queries:
        q = (query or "").strip()
        if not q or q.lower() in seen_q:
            continue
        seen_q.add(q.lower())
        intent_topic = _lookup_intent_topic(client, q)
        if intent_topic:
            break

    binding: dict[str, Any] = {
        "hg_product_id": None,
        "hg_product_name": None,
        "hg_vendor_id": None,
        "hg_vendor_name": None,
        "hg_category_id": None,
        "hg_category_name": None,
        "hg_intent_topic_id": None,
        "hg_intent_topic_name": None,
        "hg_catalog_match_examples": examples,
        "binding_confidence": "low",
        "binding_notes": [],
    }

    if catalog_pick:
        binding["hg_product_id"] = str(catalog_pick.get("product_id") or "") or None
        binding["hg_product_name"] = catalog_pick.get("product_name")
        binding["hg_vendor_name"] = catalog_pick.get("vendor_name")
        binding["binding_confidence"] = "high" if binding["hg_product_id"] else "medium"
    else:
        binding["binding_notes"].append(
            "No HG vendor catalog SKU matched; PRS intent/momentum may need manual product_name."
        )

    if category:
        binding["hg_category_id"] = category.get("id")
        binding["hg_category_name"] = category.get("name")
        if binding["binding_confidence"] == "low":
            binding["binding_confidence"] = "medium"
    else:
        binding["binding_notes"].append(
            "HG category not resolved via list_product_categories; need criterion may be unreliable."
        )

    if intent_topic:
        binding["hg_intent_topic_id"] = intent_topic.get("id")
        binding["hg_intent_topic_name"] = intent_topic.get("name")
    else:
        binding["binding_notes"].append(
            "HG intent topic not resolved; purchase intent criterion defaults to 0."
        )

    if binding["hg_product_id"] and binding["hg_category_name"] and binding["hg_intent_topic_name"]:
        binding["binding_confidence"] = "high"

    competitor_query = binding.get("hg_product_name") or product_name
    competitors, competitor_resolution = _resolve_hg_competitors(client, competitor_query)
    binding["hg_competitor_products"] = competitors
    binding["competitor_resolution"] = competitor_resolution
    if not competitors:
        binding["binding_notes"].append(
            "No HG competitor SKUs resolved from accepted get_product_information competitor/alternative fields "
            "(stored for audit only; not used in PRS)."
        )

    return binding


def build_prs_methodology_block(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "methodology_version": "1.0",
        "methodology_document": "la-methodologie.md",
        "prs_formula": (
            "PRS = 0.25*S_taille + 0.20*S_budget + 0.20*S_besoin "
            "+ 0.20*S_achat + 0.15*S_dynamique"
        ),
        "reliability_formula": (
            "R_global = weighted sum of per-criterion reliability; "
            "renormalize if a criterion is skipped"
        ),
        "weights": PRS_WEIGHTS,
        "criteria": PRS_CRITERIA_SPEC,
        "prospect_mcp_calls_per_account": [
            {
                "order": 1,
                "tool": "company_firmographic",
                "used_for": ["taille"],
            },
            {
                "order": 2,
                "tool": "company_spend",
                "used_for": ["budget"],
                "notes": "Use Total IT line totalSpendAmount when available",
            },
            {
                "order": 3,
                "tool": "company_technographic",
                "used_for": ["besoin"],
                "params": {
                    "product_name": binding.get("hg_product_name"),
                    "category_name": binding.get("hg_category_name"),
                },
            },
            {
                "order": 4,
                "tool": "company_intent",
                "used_for": ["achat"],
                "params": {
                    "product_name": binding.get("hg_intent_topic_name")
                    or binding.get("hg_product_name"),
                },
            },
            {
                "order": 5,
                "tool": "company_install_time_series",
                "used_for": ["dynamique"],
                "params": {"products": [binding.get("hg_product_id")]},
            },
        ],
        "scoring_scope": "prospect_accounts_only",
        "seller_profile_role": (
            "Provides product binding and vendor context; all quantitative scores "
            "are computed from prospect MCP data."
        ),
    }


def build_ideal_customer_profile(
    firmo: dict[str, Any],
    binding: dict[str, Any],
    selected: dict[str, Any],
    floor_overrides: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Lightweight ICP for prospect pool retrieval (not PRS).
    Numeric floors come from user input at seller profile setup when provided.
    """
    if floor_overrides:
        min_revenue = int(floor_overrides["min_revenue_usd"])
        min_employees = int(floor_overrides["min_employees"])
        min_it_spend = int(floor_overrides["min_it_spend_usd"])
        floors_user_defined = True
    else:
        revenue = firmo.get("revenue") or firmo.get("revenueAmount") or 0
        employees = firmo.get("employeeCount") or firmo.get("employees") or 0
        it_spend = firmo.get("itSpend") or firmo.get("it_spend") or 0

        try:
            revenue_f = float(revenue)
        except (TypeError, ValueError):
            revenue_f = 0.0
        try:
            employees_i = int(employees)
        except (TypeError, ValueError):
            employees_i = 0
        try:
            it_spend_f = float(it_spend)
        except (TypeError, ValueError):
            it_spend_f = 0.0

        min_revenue = max(50_000_000, revenue_f * 0.0001) if revenue_f > 0 else 50_000_000
        min_employees = max(200, int(employees_i * 0.00005)) if employees_i > 0 else 500
        min_it_spend = max(2_000_000, it_spend_f * 0.0001) if it_spend_f > 0 else 2_000_000
        floors_user_defined = False

    category_name = binding.get("hg_category_name") or selected.get("product_category")
    product_name = binding.get("hg_product_name") or selected.get("product_name")

    floor_rationale = (
        "Threshold entered by the sales user when creating the seller profile."
        if floors_user_defined
        else "Default floor (non-interactive run or legacy profile without user floors)."
    )

    return {
        "purpose": "Filter prospect universe before PRS; does not replace PRS scoring.",
        "derived_from_seller_profile": not floors_user_defined,
        "user_defined_floors": floors_user_defined,
        "filters": [
            {
                "filter_id": "min_revenue_usd",
                "operator": ">=",
                "value": round(min_revenue),
                "hg_field": "company_firmographic.revenue",
                "rationale": floor_rationale,
            },
            {
                "filter_id": "min_employees",
                "operator": ">=",
                "value": min_employees,
                "hg_field": "company_firmographic.employeeCount",
                "rationale": floor_rationale,
            },
            {
                "filter_id": "min_it_spend_usd",
                "operator": ">=",
                "value": round(min_it_spend),
                "hg_field": "company_spend.totalSpendAmount (Total IT)",
                "rationale": floor_rationale,
            },
            {
                "filter_id": "category_adjacency_search",
                "operator": "technographic_signal",
                "value": category_name,
                "hg_field": "company_technographic.categories / search_companies",
                "rationale": (
                    "Prospects should show activity in the same HG category as the sold product "
                    "to avoid scoring random accounts with zero category fit."
                ),
            },
            {
                "filter_id": "exclude_target_product_installed",
                "operator": "excludeTechnologies",
                "value": product_name,
                "hg_field": "search_companies.excludeTechnologies",
                "rationale": (
                    "Land motion only: exclude accounts where the seller HG SKU is already installed."
                ),
            },
        ],
        "product_context": {
            "hg_product_name": product_name,
            "note": (
                "Seller SKU exclusion is enforced at universe retrieval (land motion)."
            ),
        },
    }


def enrich_seller_profile_for_methodology(
    client: HgMcpClient,
    selected: dict[str, Any],
    company_name: str,
    domain: str,
    vendor_summary: dict[str, Any],
    firmo: dict[str, Any],
    floor_overrides: dict[str, int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    binding = build_hg_product_binding(client, selected, company_name, domain, vendor_summary)
    prs_block = build_prs_methodology_block(binding)
    icp_block = build_ideal_customer_profile(firmo, binding, selected, floor_overrides)
    return binding, prs_block, icp_block
