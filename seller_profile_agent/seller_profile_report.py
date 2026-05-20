"""Render seller_profile.md — seller company + product binding for interview prep."""

from __future__ import annotations

from typing import Any

from methodology_formulas import GLOBAL_RELIABILITY_FORMULA, GLOBAL_SCORE_FORMULA
from report_format import fmt_money


def render_seller_profile_md(seller: dict[str, Any]) -> str:
    selected = seller.get("selected_product") or {}
    binding = selected.get("hg_binding") or {}
    competitor_resolution = binding.get("competitor_resolution") or {}
    icp = seller.get("ideal_customer_profile") or {}
    raw = seller.get("raw_hg_data_used") or {}
    firmo = raw.get("firmographic") or {}
    rev = firmo.get("revenue") or firmo.get("revenueAmount")
    emp = firmo.get("employeeCount") or firmo.get("employees")
    it_spend = firmo.get("itSpend") or firmo.get("it_spend")
    domain = raw.get("resolved_domain") or firmo.get("domain") or "N/A"

    lines = [
        "# Seller Profile",
        "",
        "This document is the **source of truth** for how the seller account and the selected "
        "product line drive HG queries, ICP thresholds, and Prospect Revenue Score criteria. "
        "The executive summary references this file instead of repeating full seller detail.",
        "",
        "## 1. Seller company (HG firmographics)",
        "",
        f"| Field | HG source | Value |",
        f"|-------|-----------|-------|",
        f"| Company | `company_firmographic` | {seller.get('company_name', '')} |",
        f"| Domain | `company_firmographic.domain` | `{domain}` |",
        f"| Industry | `company_firmographic.industry` | {seller.get('industry', 'N/A')} |",
        f"| Revenue | `company_firmographic.revenue` | {fmt_money(rev)} |",
        f"| Employees | `company_firmographic.employeeCount` | {emp or 'N/A'} |",
        f"| IT spend | `company_firmographic.itSpend` | {fmt_money(it_spend)} |",
        "",
        "### Why these seller fields matter",
        "",
        "- **`revenue` and `employeeCount`** calibrate the **Company Size Fit** anchor on prospects.",
        "- **ICP numeric floors** (`min_revenue_usd`, `min_employees`, `min_it_spend_usd`) are "
        "**entered by the sales user** when running `npm run profile:seller` — not derived from formulas.",
        "- **`technologies_detected`** is a short sample from seller technographics — it does **not** "
        "build the product line menu (see `seller_profile.md` §2).",
        "",
        f"**Business context:** {seller.get('business_description', 'N/A')}",
        "",
        "## 2. Sellable product lines (how the menu was built)",
        "",
        f"The profile lists **{len(seller.get('available_products') or [])}** lines in "
        "`available_products` (max 20). They come from HG `get_vendor_information` + deterministic "
        "regex in `product_discovery.py` — **not** from an LLM and **not** from seller install data.",
        "",
        "Each line has a `source_type`: `HG data` (catalog-backed), `inferred from HG data`, or "
        "`general business inference` (weak fallback). **Honest limit:** regex families are "
        "cloud-oriented; non-cloud sellers often get noisy `HG catalog product` rows.",
        "",
        "Full step-by-step notes are in **§2** above and in `candidate_companies.md` for ICP application.",
        "",
        "## 3. Selected product line & HG binding",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Product line sold | {selected.get('product_name', '')} |",
        f"| HG SKU | `{binding.get('hg_product_name', '')}` (id: `{binding.get('hg_product_id', '')}`) |",
        f"| HG category | `{binding.get('hg_category_name', '')}` |",
        f"| Intent topic (HG) | `{binding.get('hg_intent_topic_name', '')}` |",
        f"| Binding confidence | {binding.get('binding_confidence', '')} |",
        "",
        "### Product-specific HG features used in scoring",
        "",
        "| Criterion | MCP tool | HG fields driven by this product binding |",
        "|-----------|----------|------------------------------------------|",
        f"| Technology Category Need | `company_technographic` | Max `intensity` in **`{binding.get('hg_category_name', '')}`** |",
        f"| Purchase Intent Signal | `company_intent` | Topic **`{binding.get('hg_intent_topic_name', '')}`** → `topics[].score`, `topics[].last_seen_at` |",
        f"| Product Adoption Momentum | `company_install_time_series` | `intensity_momentum` for target SKU |",
        "",
        "These bindings are **differentiating**: changing the selected product changes which HG "
        "product, category, and intent topic are queried — and therefore changes need, intent, and momentum "
        "for every prospect.",
        "",
        "### Competitor extraction audit",
        "",
        f"- Tool/method: `{competitor_resolution.get('method', 'get_product_information(includeCompetitors=True)')}`",
        f"- Query product: `{competitor_resolution.get('query_product_name', binding.get('hg_product_name', ''))}`",
        f"- Status: `{competitor_resolution.get('status', 'not available on older profile')}`",
        f"- Competitor products extracted: **{competitor_resolution.get('normalized_count', len(binding.get('hg_competitor_products') or []))}**",
        "- Accepted fields are explicit competitor/alternative product fields only; no competitors are guessed from free text.",
        "",
        "## 4. ICP thresholds (prospect universe — not the PRS score)",
        "",
        "Four filters are defined in `ideal_customer_profile.filters`. Three numeric floors are "
        "**user-defined at seller profile setup**; the fourth is a **technographic search rule**.",
        "",
    ]

    for f in icp.get("filters") or []:
        hg_field = f.get("hg_field", "")
        lines.append(
            f"- **{f.get('filter_id')}** {f.get('operator', '')} {f.get('value')} "
            f"— HG field: `{hg_field}`. {f.get('rationale', '')}"
        )

    lines.extend(
        [
            "",
            "**Why 3 numeric ICP lines + 1 search rule:** revenue, employee, and IT spend floors are "
            "thresholds you set in the terminal when creating the seller profile. "
            "**category_adjacency_search** restricts `search_companies` to accounts tagged with the "
            "seller product's HG category.",
            "",
            "## 5. Differentiating elements for interview discussion",
            "",
            "**Seller-side (profile granularity):**",
            "",
            f"1. **Product binding** — SKU `{binding.get('hg_product_name', '')}` and category "
            f"`{binding.get('hg_category_name', '')}` define what “installed” and “need” mean.",
            f"2. **Intent topic** — `{binding.get('hg_intent_topic_name', '')}` must exist in HG; "
            "if wrong, Purchase Intent collapses to 0 with 0% reliability.",
            "3. **ICP floors** — derived ratios vs seller revenue/employees/IT spend (see JSON values).",
            "4. **Binding confidence** — whether HG catalog match was exact or approximate.",
            "",
            "**Prospect-side (differentiating data per account):**",
            "",
            "- `company_firmographic.revenue` / `employeeCount` → Company Size Fit",
            "- `company_spend` Total IT → Estimated IT Budget Capacity",
            "- Category intensities → Technology Category Need",
            "- Intent topic score + freshness → Purchase Intent Signal",
            "- `intensity_momentum` → Product Adoption Momentum",
            "",
            "## 6. Prospect Revenue Score formula reference",
            "",
            GLOBAL_SCORE_FORMULA,
            "",
            GLOBAL_RELIABILITY_FORMULA,
            "",
            "PRS criterion math and worked examples: `technical_scoring.md`.",
            "",
        ]
    )

    return "\n".join(lines)
