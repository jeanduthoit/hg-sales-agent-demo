"""ICP candidate funnel narratives for executive reports."""

from __future__ import annotations

from typing import Any

from report_format import fmt_money


def _company_label(row: dict[str, Any]) -> str:
    return (
        row.get("companyName")
        or row.get("company_name")
        or row.get("domain")
        or row.get("companyDomain")
        or "Unknown"
    )


def build_icp_funnel_context(
    universe_companies: list[dict[str, Any]],
    shortlist_stats: dict[str, Any],
    seller: dict[str, Any],
) -> dict[str, Any]:
    """Summarize who was scanned, who passed ICP gates, and who was eliminated."""
    icp = shortlist_stats.get("icp_thresholds") or {}
    min_rev = float(icp.get("min_revenue", 0))
    min_emp = int(icp.get("min_employees", 0))
    min_it = float(icp.get("min_it_spend", 0))

    analyzed = [
        {"name": _company_label(r), "domain": (r.get("domain") or r.get("companyDomain") or "").lower()}
        for r in universe_companies
    ]

    eliminated = shortlist_stats.get("eliminated_by_threshold") or []
    passed_count = shortlist_stats.get("after_hard_filter", 0)

    return {
        "universe_count": len(universe_companies),
        "analyzed_companies": analyzed,
        "analyzed_names_inline": ", ".join(a["name"] for a in analyzed),
        "min_revenue_usd": min_rev,
        "min_employees": min_emp,
        "min_it_spend_usd": min_it,
        "category": icp.get("category"),
        "eliminated": eliminated,
        "eliminated_count": len(eliminated),
        "passed_icp_count": shortlist_stats.get("candidate_count", passed_count),
        "input_after_hygiene": shortlist_stats.get("after_hygiene", 0),
        "sample": shortlist_stats.get("sample") or {},
        "deep_prs": shortlist_stats.get("deep_prs") or {},
    }


def render_icp_funnel_section(ctx: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    n = ctx["universe_count"]
    min_rev = ctx["min_revenue_usd"]
    min_emp = ctx["min_employees"]
    min_it = ctx["min_it_spend_usd"]

    lines.append(
        f"**{n} companies** returned by HG `search_companies` and reviewed against the "
        f"Ideal Customer Profile thresholds from `icp_thresholds.json`."
    )
    lines.append("")
    if ctx.get("analyzed_names_inline"):
        lines.append(f"Companies in this scan: {ctx['analyzed_names_inline']}.")
        lines.append("")

    lines.append(
        "**ICP thresholds applied** (set at seller profile setup; full list: `candidate_companies.md`)"
    )
    lines.append("")
    lines.append(f"- Minimum revenue: **{fmt_money(min_rev)}** (user-defined `min_revenue_usd`)")
    lines.append(f"- Minimum employees: **{min_emp:,}** (user-defined `min_employees`)")
    lines.append(
        f"- Minimum IT spend: **{fmt_money(min_it)}** "
        "(user-defined `min_it_spend_usd`; enforced when present in search data, fully measured during PRS)"
    )
    if ctx.get("category"):
        lines.append(f"- Product/category adjacency: **{ctx['category']}** (`search_companies.technologies`)")
    lines.append("")

    elim = ctx.get("eliminated") or []
    if elim:
        lines.append(f"**{len(elim)} companies eliminated** by deterministic ICP filters:")
        lines.append("")
        for row in elim[:25]:
            rev_s = fmt_money(row.get("revenue")) if row.get("revenue") is not None else "unknown"
            emp_s = row.get("employees") if row.get("employees") is not None else "unknown"
            failed = ", ".join(row.get("failed_filters") or [])
            lines.append(
                f"- **{row.get('company_name')}** (`{row.get('domain')}`) — "
                f"revenue {rev_s}, employees {emp_s}; failed: {failed}"
            )
        if len(elim) > 25:
            lines.append(f"- … and {len(elim) - 25} more (see `candidate_companies.json`).")
        lines.append("")
    else:
        lines.append(
            "No additional eliminations after the HG search response — returned accounts were "
            "kept as ICP-compatible candidates without scoring or ordering."
        )
        lines.append("")

    lines.append(
        f"After hygiene and ICP gates, **{ctx.get('passed_icp_count', 0)} companies** remained in "
        "`candidate_companies.json`. No PRS, score, weight, rank, or ordering exists at this stage."
    )
    lines.append("")
    return lines


def render_sampling_section(shortlist_stats: dict[str, Any]) -> list[str]:
    """Random sample trace — selection before PRS, not a ranking."""
    sample = shortlist_stats.get("sample") or {}
    deep = shortlist_stats.get("deep_prs") or {}
    lines: list[str] = [
        "### Random sample before PRS — not a ranking",
        "",
        "The pipeline randomly samples from ICP-compatible candidates **before** any deep PRS call. "
        "This avoids hidden prioritization layers and keeps discovery explainable.",
        "",
        f"- ICP-compatible candidates: **{sample.get('candidate_count', shortlist_stats.get('candidate_count', 0))}**",
        f"- Requested deep PRS count: **{sample.get('requested_count', deep.get('requested_count', 0))}**",
        f"- Randomly sampled: **{sample.get('sampled_count', 0)}**",
        f"- Successfully scored with full PRS: **{deep.get('scored_count', 0)}**",
        f"- Sampling method: `{sample.get('sample_method', 'uniform_random_without_replacement')}`",
    ]
    if sample.get("sample_seed") is not None:
        lines.append(f"- Sample seed: `{sample.get('sample_seed')}`")
    skipped = deep.get("skipped") or []
    if skipped:
        lines.append(f"- Skipped during deep PRS: **{len(skipped)}** (see `scoring_manifest.json`)")
    lines.extend(
        [
            "",
            "**How to read this:** the only ranking in the project is the PRS ranking after deep "
            "analysis. The sample file records who was selected, not who was better.",
            "",
        ]
    )
    return lines
