"""Cross-prospect comparative intelligence (deterministic)."""

from __future__ import annotations

from typing import Any

from methodology_formulas import PROSPECT_REVENUE_SCORE_NAME
from prs_criteria import CRITERION_ORDER
from prs_engine import ProspectScore
from report_format import criterion_score_label, score_display


def _criterion_values(results: list[ProspectScore], cid: str) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for p in results:
        c = p.criteria.get(cid)
        if c and c.score is not None:
            out.append((p.company_name, float(c.score)))
    return out


def _max_holder(values: list[tuple[str, float]]) -> tuple[str, float] | None:
    if not values:
        return None
    return max(values, key=lambda x: x[1])


def _min_holder(values: list[tuple[str, float]]) -> tuple[str, float] | None:
    if not values:
        return None
    return min(values, key=lambda x: x[1])


def build_comparative_insights(results: list[ProspectScore]) -> dict[str, Any]:
    """Return structured comparisons and narrative bullets."""
    bullets: list[str] = []

    prs_ranked = sorted(results, key=lambda p: p.prs, reverse=True)
    if prs_ranked:
        top = prs_ranked[0]
        bullets.append(
            f"Highest {PROSPECT_REVENUE_SCORE_NAME}: **{top.company_name}** ({prs_ranked[0].prs:.1f}/100)."
        )

    budget_vals = _criterion_values(results, "budget")
    bmax = _max_holder(budget_vals)
    if bmax:
        bullets.append(
            f"Highest Estimated IT Budget Capacity: **{bmax[0]}** "
            f"({criterion_score_label('budget', bmax[1])})."
        )

    besoin_vals = _criterion_values(results, "besoin")
    nmax = _max_holder(besoin_vals)
    if nmax:
        bullets.append(
            f"Strongest Technology Category Need: **{nmax[0]}** (intensity score {nmax[1]:.0f}/100)."
        )

    dyn_vals = _criterion_values(results, "dynamique")
    dmax = _max_holder(dyn_vals)
    if dmax and dmax[1] >= 75:
        bullets.append(
            f"Strongest Product Adoption Momentum: **{dmax[0]}** "
            f"({criterion_score_label('dynamique', dmax[1])})."
        )

    achat_vals = _criterion_values(results, "achat")
    if achat_vals:
        amin = _min_holder(achat_vals)
        amax = _max_holder(achat_vals)
        if amin and amax and amin[1] == amax[1] == 0:
            bullets.append("Weakest Purchase Intent signals: **no prospect** shows HG intent on the product topic.")
        elif amax and amax[1] > 0:
            bullets.append(f"Strongest Purchase Intent: **{amax[0]}** ({amax[1]:.0f}/100).")

    rel_ranked = sorted(results, key=lambda p: p.reliability_global, reverse=True)
    if rel_ranked:
        bullets.append(
            f"Highest PRS score reliability: **{rel_ranked[0].company_name}** "
            f"({round(rel_ranked[0].reliability_global * 100)}%)."
        )
        bullets.append(
            f"Lowest PRS score reliability in cohort: **{rel_ranked[-1].company_name}** "
            f"({round(rel_ranked[-1].reliability_global * 100)}%)."
        )

    return {
        "bullets": bullets,
        "by_criterion": {
            cid: {
                "max": _max_holder(_criterion_values(results, cid)),
                "min": _min_holder(_criterion_values(results, cid)),
            }
            for cid in CRITERION_ORDER
        },
    }
