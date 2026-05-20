"""PRS criterion metadata — English labels and business explanations."""

from __future__ import annotations

from typing import Any

# Internal keys unchanged for formula compatibility; display names are English.
CRITERION_ORDER = [
    "taille",
    "budget",
    "besoin",
    "achat",
    "dynamique",
]

CRITERION_META: dict[str, dict[str, Any]] = {
    "taille": {
        "display_name": "Company Size Fit",
        "weight": 0.25,
        "input_fields": ["revenue_usd", "employee_count"],
        "summary": "Structural revenue ceiling for deal size (log-scaled revenue vs linear employees).",
    },
    "budget": {
        "display_name": "Estimated IT Budget Capacity",
        "weight": 0.20,
        "input_fields": ["it_budget_usd", "unknown_row_count"],
        "summary": "Ability to fund IT projects from HG Total IT spend or firmographic IT spend.",
    },
    "besoin": {
        "display_name": "Technology Category Need",
        "weight": 0.20,
        "input_fields": ["category_name", "max_category_intensity"],
        "summary": "Strength of activity in the seller product's HG category (ecosystem fit).",
    },
    "achat": {
        "display_name": "Purchase Intent Signal",
        "weight": 0.20,
        "input_fields": ["intent_topic", "intent_score", "last_seen_at", "freshness_multiplier"],
        "summary": "HG intent score on the product topic, discounted by signal age.",
    },
    "dynamique": {
        "display_name": "Product Adoption Momentum",
        "weight": 0.15,
        "input_fields": ["intensity_momentum", "time_series_found"],
        "summary": (
            "HG intensity_momentum on the bound seller SKU (24-month install time series): "
            "rising (>0), flat (=0), or declining (<0) — not company revenue growth."
        ),
    },
}


def display_name(criterion_id: str) -> str:
    return CRITERION_META.get(criterion_id, {}).get("display_name", criterion_id)
