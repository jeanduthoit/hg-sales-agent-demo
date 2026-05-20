"""Executive Sales Intelligence Report — iteration-based outputs."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from comparative_insights import build_comparative_insights
from icp_funnel import (
    build_icp_funnel_context,
    render_icp_funnel_section,
)
from iteration_manager import slugify_run_name
from methodology_formulas import (
    GLOBAL_SCORE_FORMULA,
    PROSPECT_REVENUE_SCORE_NAME,
    PRS_FORMULA_BULLETS,
    WEIGHTED_RELIABILITY_LABEL,
)
from prs_criteria import CRITERION_ORDER, display_name
from prs_engine import ProspectScore
from report_format import (
    fmt_money,
    format_criterion_reliability_line,
    prospect_revenue_score_line,
    reliability_pct,
    score_display,
)
from sales_insights import build_prospect_card


def _render_icp_vs_seller_clarity(seller_profile: dict[str, Any], icp_ctx: dict[str, Any] | None) -> str:
    """
    Prevent readers from confusing user-entered ICP floors with the seller's own HG firmographics.
    """
    icp_meta = seller_profile.get("ideal_customer_profile") or {}
    user_defined = bool(icp_meta.get("user_defined_floors"))
    user_floors = seller_profile.get("icp_user_floors") or {}

    lines: list[str] = [
        "### ICP thresholds vs seller company (HG)",
        "",
    ]
    if user_defined:
        lines.extend(
            [
                "The **minimum revenue, employee count, and IT spend** applied to **prospect** `search_companies` "
                "are the **Ideal Customer Profile floors you entered** when building the seller profile. "
                "They describe **who you want to sell to**, not the seller firm’s own HG revenue or headcount "
                "(unless you intentionally typed the same numbers).",
                "",
            ]
        )
        if user_floors:
            lines.append("**Your ICP floors (inputs):**")
            lines.append("")
            mr = user_floors.get("min_revenue_usd")
            me = user_floors.get("min_employees")
            mit = user_floors.get("min_it_spend_usd")
            if mr is not None:
                lines.append(f"- Minimum revenue (prospect filter): **{fmt_money(mr)}**")
            if me is not None:
                lines.append(f"- Minimum employees (prospect filter): **{int(me):,}**")
            if mit is not None:
                lines.append(f"- Minimum IT spend (prospect filter): **{fmt_money(mit)}**")
            lines.append("")
    else:
        lines.extend(
            [
                "Numeric ICP floors in `ideal_customer_profile` were **derived heuristically** from the seller’s "
                "HG firmographics (legacy / non-interactive profile build), not typed by you. "
                "See `seller_profile.json` → `ideal_customer_profile`.",
                "",
            ]
        )

    raw = seller_profile.get("raw_hg_data_used") or {}
    firmo = raw.get("firmographic") or {}
    rev = firmo.get("revenue") or firmo.get("revenueAmount")
    emp = firmo.get("employeeCount") or firmo.get("employees")
    it_sp = firmo.get("itSpend") or firmo.get("it_spend")

    lines.append("**Seller company — HG firmographics (reference only, not your ICP input):**")
    lines.append("")
    lines.append("| Field | Value (HG) |")
    lines.append("|-------|------------|")
    rev_cell = fmt_money(rev) if rev not in (None, "") else "N/A"
    try:
        emp_cell = f"{int(float(emp)):,}" if emp not in (None, "") else "N/A"
    except (TypeError, ValueError):
        emp_cell = str(emp) if emp not in (None, "") else "N/A"
    it_cell = fmt_money(it_sp) if it_sp not in (None, "") else "N/A"
    if rev_cell == "N/A" and seller_profile.get("revenue_range"):
        rev_cell = str(seller_profile.get("revenue_range"))
    if emp_cell == "N/A" and seller_profile.get("company_size"):
        emp_cell = str(seller_profile.get("company_size"))
    lines.append(f"| Revenue | {rev_cell} |")
    lines.append(f"| Employees | {emp_cell} |")
    lines.append(f"| IT spend (firmographic, if present) | {it_cell} |")
    lines.append("")

    if icp_ctx:
        lines.append("**How prospects were filtered this run:**")
        lines.append("")
        lines.extend(render_icp_funnel_section(icp_ctx))
    return "\n".join(lines)


def _prospect_to_json(prospect: ProspectScore, card: dict[str, Any]) -> dict[str, Any]:
    criteria_out: dict[str, Any] = {}
    for cid in CRITERION_ORDER:
        c = prospect.criteria.get(cid)
        if not c:
            continue
        json_key = display_name(cid).lower().replace(" ", "_")
        criteria_out[json_key] = {
            "display_name": display_name(cid),
            "score": c.score,
            "reliability_pct": reliability_pct(c.reliability),
            "reliability_raw": round(c.reliability, 4),
            "weight": c.weight,
            "contribution": round(c.contribution, 2),
            "raw_inputs": {k: v for k, v in c.inputs.items() if k not in ("explanation", "display_name")},
            "explanation": c.inputs.get("explanation", ""),
        }
    return {
        "rank": prospect.rank,
        "company_name": prospect.company_name,
        "domain": prospect.domain,
        "prospect_revenue_score": round(prospect.prs, 2),
        "reliability_pct": reliability_pct(prospect.reliability_global),
        "reliability_raw": round(prospect.reliability_global, 4),
        "sales_card": card,
        "criteria": criteria_out,
        "notes": prospect.raw_notes,
    }


def _render_executive_summary(
    iteration_title: str,
    seller_meta: dict[str, Any],
    seller_profile: dict[str, Any],
    results: list[ProspectScore],
    cards: list[dict[str, Any]],
    comparative: dict[str, Any],
    icp_ctx: dict[str, Any] | None,
    shortlist_stats: dict[str, Any] | None = None,
) -> str:
    seller = seller_profile.get("company_name") or seller_meta.get("company_name")
    product = seller_meta.get("target_product")
    n = len(results)

    candidate_count = None
    if shortlist_stats:
        candidate_count = shortlist_stats.get("candidate_count")
        if candidate_count is None:
            candidate_count = shortlist_stats.get("after_hard_filter")

    lines = [
        "# Executive Sales Intelligence Report",
        f"## {iteration_title}",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        f"This report prioritizes **{n} prospects** for **{seller}** selling **{product}** "
        f"(HG SKU: `{seller_meta.get('hg_product_name', '')}`).",
        "",
        (
            f"ICP filtering produced **{candidate_count} ICP-compatible candidate companies** "
            "documented in `candidate_companies.md`."
            if candidate_count is not None
            else "ICP-compatible candidate companies are documented in `candidate_companies.md`."
        ),
        "",
        "**Global formula:**",
        "",
        "- Prospect Revenue Score =",
    ]
    for weight, name, definition in PRS_FORMULA_BULLETS:
        lines.append(f"- {weight} **{name}** — {definition}")
    lines.append("")
    lines.append(_render_icp_vs_seller_clarity(seller_profile, icp_ctx))
    lines.append("")

    lines.extend(["### Randomly Picked Companies From ICP Candidates", ""])
    if results:
        for i, p in enumerate(results[:3], start=1):
            lines.append(
                f"{i}. **{p.company_name}** — Prospect Revenue Score {score_display(p.prs)}/100, "
                f"PRS score reliability {reliability_pct(p.reliability_global)}"
            )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Prospect Ranking Overview",
            "",
        "Only randomly sampled accounts with a full Prospect Revenue Score appear here, sorted by PRS descending.",
            "",
        ]
    )
    lines.append("| Rank | Company | Prospect Revenue Score (/100) | PRS score reliability |")
    lines.append("|------|---------|-------------------------------|-------------------|")
    for p in results:
        lines.append(
            f"| {p.rank} | {p.company_name} | {score_display(p.prs)} | "
            f"{reliability_pct(p.reliability_global)} |"
        )
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def _render_impact_section_brief(
    seller_meta: dict[str, Any],
    seller_profile: dict[str, Any],
) -> str:
    selected = seller_profile.get("selected_product") or {}
    binding = selected.get("hg_binding") or {}
    category = binding.get("hg_category_name") or selected.get("product_category") or ""
    icp_meta = seller_profile.get("ideal_customer_profile") or {}
    user_defined = bool(icp_meta.get("user_defined_floors"))
    if user_defined:
        icp_floors_explain = (
            "- **ICP numeric floors** (minimum prospect revenue / employees / IT spend) → **the thresholds you typed** "
            "for your Ideal Customer Profile when building `seller_profile.json`. HG applies them to **prospects** via "
            "`search_companies` (`revenueMin`, `employeesMin`, row checks) and deep `company_spend` for PRS. "
            "**They are not the seller company’s own HG firmographic headcount or revenue unless you matched them on purpose.** "
            "See the Executive Summary section above for a side-by-side with seller HG firmographics."
        )
    else:
        icp_floors_explain = (
            "- **ICP numeric floors** → derived heuristically from the seller’s HG firmographics when no user floors exist "
            "(legacy / non-interactive build). See `ideal_customer_profile` in `seller_profile.json` and the Executive Summary above."
        )
    lines = [
        "## 3. Seller Product Impact Analysis",
        "",
        "Elements from `seller_profile.json` that **directly change** scores:",
        "",
        "### ICP candidate filtering inputs",
        "",
        f"- **Seller product excluded from candidates** (`{binding.get('hg_product_name', '')}`) → excluded at ICP via "
        "`search_companies.excludeTechnologies`, so the candidate pool focuses on accounts that do not already use the sold product.",
        icp_floors_explain,
        f"- **Product sold by the sales user:** {selected.get('product_name', '')} → chosen during seller profile setup (CLI or Streamlit).",
        "  - `methodology_binding.py` matches this business label to HG catalog data: product/SKU, category, intent topic, and competitor products.",
        "  - It then uses those HG parameters to build the ICP filters used by `search_companies`.",
        "",
        "### Deep PRS scoring inputs",
        "",
        f"- **Technology category used to measure need** (`{category}`) → used for Technology Category Need; during deep scoring, "
        "`company_technographic` reads installed products/categories and their intensity in this category.",
        f"- **Buying-intent topic to look for** (`{binding.get('hg_intent_topic_name', '')}`) → used for Purchase Intent Signal; "
        "during deep scoring, `company_intent` reads `topics[].score` and `topics[].last_seen_at` for this topic.",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def _commercial_brief_bullets(card: dict[str, Any]) -> list[str]:
    """Flat analysis bullets — no Strengths / Weaknesses sub-headings."""
    lines: list[str] = []
    positives = card.get("sales_positive_signals") or []
    risks = card.get("sales_risk_signals") or []

    for item in positives:
        lines.append(item if item.startswith("-") else f"- {item}")

    if not positives:
        lines.append(
            "- No major positive HG signal beyond ICP compatibility and completed PRS scoring."
        )

    for item in risks:
        lines.append(item if item.startswith("-") else f"- {item}")

    if not risks and positives:
        lines.append("- No critical risk flagged with HG evidence.")

    return lines


def _render_prospect_cards(cards: list[dict[str, Any]]) -> str:
    lines = ["## 4. Prospect Cards", ""]
    for card in cards:
        lines.extend([
            f"### #{card['rank']} — {card['company_name']}",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Prospect Revenue Score (/100) | {card['prs_display']} |",
            f"| PRS score reliability | {card['reliability_pct']} |",
            "",
            "#### PRS Score Details (full calculations: `technical_scoring.md`)",
            "",
            card["prospect_revenue_score_line"],
            "",
        ])
        for line in card.get("prs_calculation_lines") or []:
            lines.append(line)
        lines.extend([
            "",
            "#### PRS Score Reliability",
            "",
        ])
        for rl in card.get("reliability_detail_lines") or []:
            lines.append(rl)
        lines.append("")
        lines.append("#### Commercial Brief (HG-Evidenced)")
        lines.append("")
        for line in _commercial_brief_bullets(card):
            lines.append(line)
        lines.append("")
        timing = card.get("timing", "")
        if timing.startswith("HG purchase intent supports"):
            lines.append("**Timing**")
            lines.append("")
            lines.append(f"- {timing}")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _render_comparative(comparative: dict[str, Any]) -> str:
    lines = ["## 5. Comparative Insights (this scan)", ""]
    for b in comparative.get("bullets") or []:
        lines.append(f"- {b}")
    lines.append("")
    return "\n".join(lines)


def _render_technical_scoring(
    seller_meta: dict[str, Any],
    results: list[ProspectScore],
) -> str:
    lines = [
        "# Technical Scoring Details",
        "",
        "## Per-prospect calculations",
        "",
        f"Seller: {seller_meta.get('company_name')} | Product: {seller_meta.get('target_product')}",
        "",
    ]
    for p in results:
        lines.append(f"### {p.company_name} (`{p.domain}`)")
        lines.append("")
        lines.append(prospect_revenue_score_line(p.prs))
        lines.append("")
        lines.append(f"**{WEIGHTED_RELIABILITY_LABEL}:** {reliability_pct(p.reliability_global)}")
        lines.append("")
        for cid in CRITERION_ORDER:
            c = p.criteria.get(cid)
            if c:
                lines.append(f"- {format_criterion_reliability_line(cid, c.reliability)}")
        lines.append("")

        for cid in CRITERION_ORDER:
            c = p.criteria.get(cid)
            if not c:
                continue
            lines.append(f"#### {display_name(cid)}")
            lines.append("")
            for step in c.calculation_steps:
                if step.lower().startswith("note:") or step.lower().startswith("business read:"):
                    continue
                lines.append(f"- {step}")
            score_txt = score_display(c.score) if c.score is not None else "N/A"
            lines.append(f"- Normalized score: {score_txt}/100")
            lines.append(f"- Reliability: {reliability_pct(c.reliability)}")
            lines.append("")

        agg = p.criteria.get("_aggregate")
        if agg:
            lines.append("#### Aggregation")
            lines.append("")
            for step in agg.calculation_steps:
                if step.lower().startswith("note:"):
                    continue
                lines.append(f"- {step}")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def company_prs_output_basename(company_name: str, domain: str) -> str:
    """Filesystem-safe name, e.g. carrefour_prs.md from domain carrefour.com."""
    domain = (domain or "").lower().strip()
    if domain:
        base = domain.split(".")[0]
    else:
        base = slugify_run_name(company_name) or "company"
    base = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_") or "company"
    return f"{base}_prs.md"


def render_company_prs_report(
    seller_meta: dict[str, Any],
    seller_profile: dict[str, Any],
    prospect: ProspectScore,
    card: dict[str, Any],
) -> str:
    """Single-company PRS report: same blocks as executive_summary prospect sections."""
    seller = seller_profile.get("company_name") or seller_meta.get("company_name")
    product = seller_meta.get("target_product")

    lines = [
        f"# Prospect PRS — {prospect.company_name}",
        "",
        f"**Prospect domain:** `{prospect.domain}`",
        f"**Seller:** {seller} | **Product sold:** {product}",
        f"**HG SKU:** `{seller_meta.get('hg_product_name', '')}`",
        "",
        "---",
        "",
        "## 1. Prospect summary",
        "",
        f"Deep PRS for **{prospect.company_name}** (`{prospect.domain}`), using the seller profile binding "
        f"in `seller_profile.json`.",
        "",
        "**Global formula:**",
        "",
        "- Prospect Revenue Score =",
    ]
    for weight, name, definition in PRS_FORMULA_BULLETS:
        lines.append(f"- {weight} **{name}** — {definition}")
    lines.append("")
    lines.append(
        f"- **{prospect.company_name}** — Prospect Revenue Score {score_display(prospect.prs)}/100, "
        f"PRS score reliability {reliability_pct(prospect.reliability_global)}"
    )
    lines.extend(["", "---", ""])

    impact = _render_impact_section_brief(seller_meta, seller_profile).replace(
        "## 3. Seller Product Impact Analysis",
        "## 2. Seller Product Impact Analysis",
        1,
    )
    lines.append(impact)

    card_block = _render_prospect_cards([card]).replace(
        "## 4. Prospect Cards",
        "## 3. Prospect card",
        1,
    )
    card_block = card_block.replace(
        "#### PRS Score Details (full calculations: `technical_scoring.md`)",
        "#### PRS Score Details (step-by-step calculations in section 4 below)",
        1,
    )
    lines.append(card_block)

    technical = _render_technical_scoring(seller_meta, [prospect])
    technical = technical.replace(
        "# Technical Scoring Details\n\n## Per-prospect calculations",
        "## 4. Technical scoring",
        1,
    )
    lines.append(technical)
    return "\n".join(lines)


def write_company_prs_report(
    output_dir: Path,
    seller_meta: dict[str, Any],
    seller_profile: dict[str, Any],
    prospect: ProspectScore,
    card: dict[str, Any],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = company_prs_output_basename(prospect.company_name, prospect.domain)
    path = output_dir / filename
    path.write_text(
        render_company_prs_report(seller_meta, seller_profile, prospect, card),
        encoding="utf-8",
    )
    return path


def write_iteration_reports(
    iteration_dir: Path,
    iteration_title: str,
    seller_meta: dict[str, Any],
    seller_profile: dict[str, Any],
    results: list[ProspectScore],
    profile_source: Path,
    pipeline_meta: dict[str, Any] | None = None,
    universe_companies: list[dict[str, Any]] | None = None,
    shortlist_stats: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """
    Write full iteration folder. Returns map of artifact name → path.
    """
    iteration_dir.mkdir(parents=True, exist_ok=True)
    comparative = build_comparative_insights(results)
    cards = [
        build_prospect_card(p, seller_meta, comparative.get("bullets"))
        for p in results
    ]

    icp_ctx = None
    if universe_companies is not None and shortlist_stats is not None:
        icp_ctx = build_icp_funnel_context(universe_companies, shortlist_stats, seller_profile)

    ranking_json = {
        "iteration": iteration_title,
        "seller": seller_meta.get("company_name"),
        "target_product": seller_meta.get("target_product"),
        "hg_product_name": seller_meta.get("hg_product_name"),
        "ranking": [
            {
                "rank": p.rank,
                "company_name": p.company_name,
                "domain": p.domain,
                "prospect_revenue_score": round(p.prs, 2),
                "reliability_pct": reliability_pct(p.reliability_global),
                "reliability_raw": round(p.reliability_global, 4),
            }
            for p in results
        ],
    }
    detailed_json = {
        "iteration": iteration_title,
        "prospects": [
            _prospect_to_json(p, cards[i]) for i, p in enumerate(results)
        ],
    }
    manifest = {
        "iteration": iteration_title,
        "documents": {},
        "pipeline": pipeline_meta or {},
        "formula": GLOBAL_SCORE_FORMULA,
    }

    paths: dict[str, Path] = {}
    for existing_name in (
        "icp_thresholds.json",
        "prospect_universe.json",
        "candidate_companies.json",
        "candidate_companies.md",
        "sampled_prospects.json",
    ):
        existing_path = iteration_dir / existing_name
        if existing_path.exists():
            paths[existing_name] = existing_path

    p = iteration_dir / "prospect_ranking.json"
    p.write_text(json.dumps(ranking_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["prospect_ranking.json"] = p

    p = iteration_dir / "detailed_prospects.json"
    p.write_text(json.dumps(detailed_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["detailed_prospects.json"] = p

    if profile_source.is_file():
        p = iteration_dir / "seller_profile.json"
        shutil.copy2(profile_source, p)
        paths["seller_profile.json"] = p

    exec_parts = [
        _render_executive_summary(
            iteration_title,
            seller_meta,
            seller_profile,
            results,
            cards,
            comparative,
            icp_ctx,
            shortlist_stats,
        ),
        _render_impact_section_brief(seller_meta, seller_profile),
        _render_prospect_cards(cards),
    ]
    p = iteration_dir / "executive_summary.md"
    p.write_text("\n".join(exec_parts) + "\n", encoding="utf-8")
    paths["executive_summary.md"] = p

    p = iteration_dir / "technical_scoring.md"
    p.write_text(_render_technical_scoring(seller_meta, results), encoding="utf-8")
    paths["technical_scoring.md"] = p

    manifest["documents"] = {k: str(v.name) for k, v in paths.items()}
    p = iteration_dir / "scoring_manifest.json"
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["scoring_manifest.json"] = p

    return paths
