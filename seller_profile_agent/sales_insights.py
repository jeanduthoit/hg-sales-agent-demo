"""Deterministic sales insights and prospect card payloads."""

from __future__ import annotations

import math
from typing import Any

from prs_criteria import CRITERION_ORDER, display_name
from prs_engine import ProspectScore
from report_format import (
    criterion_score_label,
    fmt_money,
    format_weighted_reliability_block,
    prospect_revenue_score_line,
    reliability_pct,
    score_display,
)


def _safe_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _prs_calculation_lines(prospect: ProspectScore) -> list[str]:
    """Simplified criterion-level PRS arithmetic for executive cards."""
    lines: list[str] = []
    active_weight = 0.0
    excluded: list[str] = []

    for cid in CRITERION_ORDER:
        criterion = prospect.criteria.get(cid)
        if not criterion:
            continue
        if criterion.included_in_prs and criterion.score is not None:
            active_weight += criterion.weight
            lines.append(f"- {_criterion_score_explanation(cid, criterion)}")
        else:
            excluded.append(_criterion_exclusion_explanation(cid, criterion))

    if excluded:
        lines.extend(f"- {item}" for item in excluded)
    if active_weight:
        lines.append(
            f"- Final PRS = weighted average of calculable criteria only "
            f"(active weight: {round(active_weight * 100)}%) = {score_display(prospect.prs)}/100."
        )
    return lines


def _criterion_score_explanation(cid: str, criterion: Any) -> str:
    score = score_display(criterion.score)
    inputs = criterion.inputs or {}

    if cid == "taille":
        revenue = inputs.get("revenue_usd") or inputs.get("revenue")
        employees = inputs.get("employee_count") or inputs.get("employees")
        bits: list[str] = []
        try:
            if revenue:
                rev_score = max(
                    0.0,
                    min(
                        100.0,
                        100.0 * math.log10(float(revenue) / 1_000_000) / math.log10(1000),
                    ),
                )
                bits.append(f"revenue score {score_display(rev_score)} from {fmt_money(revenue)} revenue")
        except (TypeError, ValueError):
            pass
        try:
            if employees:
                emp_score = min(100.0, 100.0 * float(employees) / 10_000.0)
                bits.append(f"employee score {score_display(emp_score)} from {int(float(employees)):,} employees")
        except (TypeError, ValueError):
            pass
        return f"Company Size Fit = {score}/100 because the score uses the stronger signal: {', '.join(bits)}."

    if cid == "budget":
        budget = inputs.get("it_budget_usd") or inputs.get("it_budget")
        return (
            f"Estimated IT Budget Capacity = {score}/100 because `company_spend` returned "
            f"Total IT spend of {fmt_money(budget)}, normalized on a log scale."
        )

    if cid == "besoin":
        category = inputs.get("category_name") or "target category"
        intensity = inputs.get("max_category_intensity")
        if intensity is None:
            intensity = inputs.get("intensity_max")
        if intensity is None:
            return (
                f"Technology Category Need = {score}/100 because the category `{category}` is known, "
                "but `company_technographic` did not return a usable installed-product intensity in that category."
            )
        return (
            f"Technology Category Need = {score}/100 because `company_technographic` returned "
            f"max product intensity {score_display(intensity)} in `{category}`."
        )

    if cid == "achat":
        topic = inputs.get("intent_topic") or "target intent topic"
        raw_score = inputs.get("intent_score") or inputs.get("topic_score")
        if raw_score is None:
            return f"Purchase Intent Signal = {score}/100 because `company_intent` returned no matched topic score for `{topic}`."
        return (
            f"Purchase Intent Signal = {score}/100 because `company_intent` returned topic score "
            f"{score_display(raw_score)} for `{topic}` after freshness adjustment."
        )

    if cid == "dynamique":
        momentum = inputs.get("intensity_momentum")
        series_found = bool(inputs.get("time_series_found") or inputs.get("series_found"))
        if not series_found:
            return (
                "Product Adoption Momentum = 50/100 because `company_install_time_series` did not find "
                "the target product; the scoring engine uses a neutral momentum value."
            )
        return f"Product Adoption Momentum = {score}/100 because `company_install_time_series` returned `intensity_momentum` = {momentum}."

    return f"{display_name(cid)} = {score}/100."


def _criterion_exclusion_explanation(cid: str, criterion: Any) -> str:
    return f"{display_name(cid)} is not included in the PRS because it is not calculable."


def _sales_positive_signals(
    prospect: ProspectScore, seller_meta: dict[str, Any]
) -> list[str]:
    hg_product = seller_meta.get("hg_product_name") or "target product"
    hg_category = seller_meta.get("hg_category_name") or "seller category"
    bullets: list[str] = []

    budget = prospect.criteria.get("budget")
    if budget and (budget.score or 0) >= 60:
        bullets.append(
            f"- **Funding capacity:** HG Total IT spend supports a meaningful infrastructure deal "
            f"({criterion_score_label('budget', budget.score)})."
        )

    taille = prospect.criteria.get("taille")
    if taille and (taille.score or 0) >= 75:
        bullets.append(
            f"- **Enterprise scale:** Revenue and headcount support a large-platform conversation "
            f"({criterion_score_label('taille', taille.score)})."
        )

    besoin = prospect.criteria.get("besoin")
    if besoin and (besoin.score or 0) >= 40:
        bullets.append(
            f"- **Category fit:** Active installs in `{hg_category}` prove they operate in your technology space "
            f"({criterion_score_label('besoin', besoin.score)})."
        )

    achat = prospect.criteria.get("achat")
    if achat and (achat.score or 0) >= 40:
        topic = seller_meta.get("hg_intent_topic_name") or "product intent topic"
        bullets.append(
            f"- **Timing signal:** HG reports recent intent on `{topic}` "
            f"({criterion_score_label('achat', achat.score)})."
        )

    return bullets[:5]


def _sales_risk_signals(prospect: ProspectScore, seller_meta: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    intent_topic = seller_meta.get("hg_intent_topic_name") or "bound intent topic"

    achat = prospect.criteria.get("achat")
    if achat and achat.reliability == 0:
        risks.append(
            f"- **No intent evidence:** HG returned no `company_intent` topic match for `{intent_topic}` — "
            "do not claim active buying signal in outreach."
        )

    besoin = prospect.criteria.get("besoin")
    if besoin and besoin.reliability < 0.5 and (besoin.score or 0) < 25:
        cat = seller_meta.get("hg_category_name") or "seller category"
        risks.append(
            f"- **Weak category footprint:** Little or no install intensity in `{cat}` in HG "
            f"({criterion_score_label('besoin', besoin.score)})."
        )

    if prospect.reliability_global < 0.6:
        risks.append(
            f"- **Data gap:** PRS score reliability {reliability_pct(prospect.reliability_global)} — "
            "validate HG spend and technographics before prospection calls."
        )

    return risks[:4]


def _precise_blockers(prospect: ProspectScore, seller_meta: dict[str, Any]) -> list[str]:
    """Only include blockers we can defend with HG evidence."""
    blockers: list[str] = []
    hg_product = seller_meta.get("hg_product_name") or "target product"
    intent_topic = seller_meta.get("hg_intent_topic_name") or ""

    budget = prospect.criteria.get("budget")
    if budget and budget.score is None:
        blockers.append(
            "HG `company_spend` did not return a usable Total IT line — budget capacity unverified."
        )

    achat = prospect.criteria.get("achat")
    if achat and achat.reliability == 0 and intent_topic:
        blockers.append(
            f"No HG intent topic matched `{intent_topic}` — timing must be built from business triggers."
        )

    return blockers


def _infrastructure_signal(prospect: ProspectScore, seller_meta: dict[str, Any]) -> str:
    hg_category = seller_meta.get("hg_category_name") or "seller HG category"
    besoin = prospect.criteria.get("besoin")
    agg = prospect.criteria.get("_aggregate")
    tech = (agg.inputs.get("mcp_evidence") or {}).get("company_technographic") if agg else {}
    product_count = tech.get("product_count") if isinstance(tech, dict) else None

    parts: list[str] = []
    if product_count is not None:
        parts.append(f"HG tracks **{product_count}** products at this domain.")
    if besoin and (besoin.score or 0) > 0:
        parts.append(
            f"Strongest signal in **`{hg_category}`**: max install intensity "
            f"{score_display(besoin.score)}/100 ({criterion_score_label('besoin', besoin.score)})."
        )
    elif besoin and besoin.reliability >= 0.5:
        parts.append(
            f"Category **`{hg_category}`** is identified but max intensity is 0 — "
            "limited proof of database-adjacent spend in HG."
        )
    else:
        parts.append(
            f"Could not confirm install intensity in **`{hg_category}`** — treat infrastructure fit as unproven."
        )
    return " ".join(parts)


def _recommended_sales_angle(prospect: ProspectScore, seller_meta: dict[str, Any]) -> str:
    product = seller_meta.get("target_product") or "target product"
    crit = prospect.criteria
    taille = crit.get("taille")
    budget = crit.get("budget")
    parts: list[str] = []

    if taille and (taille.score or 0) >= 75:
        rev = taille.inputs.get("revenue_usd") or taille.inputs.get("revenue")
        emp = taille.inputs.get("employees") or taille.inputs.get("employee_count")
        size_bits = ["Lead with an enterprise-scale conversation"]
        if rev:
            size_bits.append(f"({fmt_money(rev)} revenue")
        emp_i = _safe_int(emp)
        if emp_i is not None:
            size_bits.append(
                f", {emp_i:,} employees)" if rev else f"({emp_i:,} employees)"
            )
        else:
            size_bits.append(")")
        parts.append(
            " ".join(size_bits).replace("(,", "(").replace(" ,", ",")
            + f" — {criterion_score_label('taille', taille.score)}."
        )

    if budget and (budget.score or 0) >= 60:
        parts.append(
            f"Highlight IT budget headroom for {product} "
            f"({criterion_score_label('budget', budget.score)})."
        )

    if not parts:
        parts.append("Validate budget, category adjacency, and timing before proposing a deal structure.")

    return " ".join(parts)


def _seller_impact_bullets(seller_meta: dict[str, Any]) -> list[str]:
    return [
        f"- HG category **`{seller_meta.get('hg_category_name', '')}`** drives Technology Category Need.",
        f"- Intent topic **`{seller_meta.get('hg_intent_topic_name', '')}`** drives Purchase Intent Signal.",
        f"- Product line **{seller_meta.get('target_product', '')}** selected in `seller_profile.json`.",
    ]


def build_prospect_card(
    prospect: ProspectScore,
    seller_meta: dict[str, Any],
    comparative_bullets: list[str] | None = None,
) -> dict[str, Any]:
    product = seller_meta.get("target_product") or "target product"
    hg_label = seller_meta.get("hg_product_name") or product

    crit = prospect.criteria
    budget = crit.get("budget")
    taille = crit.get("taille")

    strategic: list[str] = []
    if taille and (taille.score or 0) >= 75:
        rev = taille.inputs.get("revenue_usd") or taille.inputs.get("revenue")
        strategic.append(
            f"Enterprise-scale account ({fmt_money(rev)} revenue signal) can support a meaningful {product} deal."
        )
    if budget and (budget.score or 0) >= 60:
        strategic.append(
            f"HG Total IT spend supports infrastructure investment "
            f"({criterion_score_label('budget', budget.score)})."
        )
    if not strategic:
        strategic.append("Moderate strategic fit — confirm budget and technographics in discovery.")

    what_to_sell = f"Lead with **{product}** (HG SKU: `{hg_label}`)."

    achat = crit.get("achat")
    if achat and (achat.score or 0) >= 40:
        timing = "HG purchase intent supports near-term outreach."
    elif achat and achat.reliability == 0:
        timing = "No HG intent on the bound topic — build timing from business triggers only."
    else:
        timing = "Timing inconclusive — confirm with stakeholders."

    blockers = _precise_blockers(prospect, seller_meta)
    pos = _sales_positive_signals(prospect, seller_meta)
    risks = _sales_risk_signals(prospect, seller_meta)

    return {
        "rank": prospect.rank,
        "company_name": prospect.company_name,
        "domain": prospect.domain,
        "prs": round(prospect.prs, 2),
        "prs_display": score_display(prospect.prs),
        "prospect_revenue_score_line": prospect_revenue_score_line(prospect.prs),
        "prs_calculation_lines": _prs_calculation_lines(prospect),
        "reliability_pct": reliability_pct(prospect.reliability_global),
        "reliability_detail_lines": format_weighted_reliability_block(prospect),
        "reliability_raw": round(prospect.reliability_global, 4),
        "best_sales_opportunity": pos[0].lstrip("- ") if pos else strategic[0],
        "weakest_fit": risks[0].lstrip("- ") if risks else "No critical risk flagged with HG evidence.",
        "recommended_sales_angle": _recommended_sales_angle(prospect, seller_meta),
        "strategic_interest": " ".join(strategic),
        "what_to_sell": what_to_sell,
        "timing": timing,
        "strongest_infrastructure_signal": _infrastructure_signal(prospect, seller_meta),
        "sale_blockers": blockers,
        "sales_positive_signals": pos,
        "sales_risk_signals": risks,
        "seller_impact_bullets": _seller_impact_bullets(seller_meta),
        "comparative_notes": comparative_bullets or [],
    }
