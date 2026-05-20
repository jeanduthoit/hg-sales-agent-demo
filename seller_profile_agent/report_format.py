"""Shared formatting for executive reports (deterministic, no qualitative buckets)."""

from __future__ import annotations

from typing import Any

from methodology_formulas import PROSPECT_REVENUE_SCORE_NAME, WEIGHTED_RELIABILITY_LABEL
from prs_criteria import CRITERION_ORDER, display_name
from prs_engine import ProspectScore
from scoring_display import fmt_num

# HG MCP field names used for reliability (la-methodologie.md / MCP tools)
RELIABILITY_FEATURES: dict[str, tuple[int, list[str]]] = {
    "taille": (2, ["company_firmographic.revenue", "company_firmographic.employeeCount"]),
    "budget": (
        2,
        ["company_spend.spendByCategory[Total IT].totalSpendAmount", "company_spend.unknownRowCount"],
    ),
    "besoin": (2, ["list_product_categories (category)", "company_technographic.products.intensity"]),
    "achat": (
        3,
        ["company_intent.topics[].score", "company_intent.topics[].last_seen_at", "intent topic match"],
    ),
    "dynamique": (1, ["company_install_time_series.products[].intensity_momentum"]),
}


def reliability_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{round(float(value) * 100)}%"


def score_display(value: float | None) -> str:
    if value is None:
        return "—"
    v = float(value)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}"


def prs_display(value: float | None) -> str:
    return score_display(value)


def criterion_score_label(criterion_id: str, score: float | None) -> str:
    name = display_name(criterion_id)
    if score is None:
        return f"{name} Score = N/A"
    return f"{name} Score = {score_display(score)}/100"


def prospect_revenue_score_line(value: float | None) -> str:
    v = score_display(value)
    return f"**{PROSPECT_REVENUE_SCORE_NAME}:** {v}/100"


def format_criterion_reliability_line(criterion_id: str, reliability: float) -> str:
    total, labels = RELIABILITY_FEATURES.get(criterion_id, (1, ["data"]))
    code_labels = [f"`{label}`" for label in labels]
    present = max(0, min(total, round(reliability * total)))
    if present == 0:
        feat = f"none among expected: {', '.join(code_labels)}"
    elif present >= total:
        feat = ", ".join(code_labels)
    else:
        feat = ", ".join(code_labels[:present]) + f" (missing: {', '.join(code_labels[present:])})"
    return (
        f"{display_name(criterion_id)}: **{present}/{total}** HG fields ({feat}) "
        f"→ reliability **{reliability_pct(reliability)}**"
    )


def format_weighted_reliability_block(prospect: ProspectScore) -> list[str]:
    lines = [
        f"**{WEIGHTED_RELIABILITY_LABEL}:** {reliability_pct(prospect.reliability_global)}",
        "",
    ]
    for cid in CRITERION_ORDER:
        c = prospect.criteria.get(cid)
        if c:
            lines.append(f"- {format_criterion_reliability_line(cid, c.reliability)}")
    return lines


def fmt_money(value: Any) -> str:
    try:
        v = float(value)
        if v >= 1_000_000_000:
            return f"${v / 1_000_000_000:.2f}B"
        if v >= 1_000_000:
            return f"${v / 1_000_000:.1f}M"
        return f"${v:,.0f}"
    except (TypeError, ValueError):
        return "N/A"
