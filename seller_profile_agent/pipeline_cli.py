#!/usr/bin/env python3
"""
3-step PRS pipeline → Executive Sales Intelligence Report (iteration folder).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from executive_reports import write_iteration_reports
from hg_client import HgMcpClient, HgMcpError
from iteration_manager import allocate_iteration, prompt_run_name, slugify_run_name
from last_run_state import load_last_profile_run
from prompt_inputs import (
    is_interactive,
    prompt_company,
    prompt_product_index,
    prompt_prs_count,
    prompt_run_folder,
)
from prospect_scorer import score_prospect
from methodology_formulas import PROSPECT_REVENUE_SCORE_NAME, WEIGHTED_RELIABILITY_LABEL
from prospect_preflight import preflight_firmographic
from report_format import fmt_money, reliability_pct
from score_cli import _load_binding
from seller_profile_builder import build_seller_profile, update_product_binding_only
from methodology_binding import MAX_SEARCH_LIMIT
from shortlist_engine import (
    build_icp_candidate_list,
    enrich_candidates_it_spend,
    fetch_prospect_universe,
    sample_icp_candidates,
)

ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "output" / "seller_profiles"
OUTPUTS_ROOT = ROOT / "outputs"


_LOG_FN: Callable[[str], None] | None = None


def _log(msg: str) -> None:
    if _LOG_FN is not None:
        _LOG_FN(msg)
    else:
        print(msg, flush=True)


def _selected_product_id(seller: dict) -> int | None:
    name = (seller.get("selected_product") or {}).get("product_name")
    for p in seller.get("available_products") or []:
        if p.get("product_name") == name:
            return p.get("id")
    return None


def _render_candidate_companies_md(
    candidates: list[dict[str, Any]],
    stats: dict[str, Any],
    seller: dict[str, Any],
    search_meta: dict[str, Any],
) -> str:
    selected = seller.get("selected_product") or {}
    binding = selected.get("hg_binding") or {}
    icp = seller.get("ideal_customer_profile") or {}
    raw = seller.get("raw_hg_data_used") or {}
    firmo = raw.get("firmographic") or {}
    filters = {item.get("filter_id"): item for item in icp.get("filters") or []}
    thresholds = stats.get("icp_thresholds") or {}
    min_revenue = thresholds.get("min_revenue", 0)
    min_employees = thresholds.get("min_employees", 0)
    min_it_spend = thresholds.get("min_it_spend", 0)
    category = thresholds.get("category") or binding.get("hg_category_name")
    product_name = binding.get("hg_product_name") or selected.get("product_name")
    hygiene = stats.get("hygiene") or {}
    attempted = (search_meta.get("queries_attempted") or [{}])[0].get("args") or {}
    category_applied = bool(attempted.get("technologies"))
    product_exclusion_applied = bool(attempted.get("excludeTechnologies"))
    missing_rows = hygiene.get("removed_missing_domain_rows") or []
    invalid_rows = hygiene.get("removed_invalid_domain_rows") or []
    duplicate_rows = hygiene.get("removed_duplicate_domain_rows") or []
    seller_rows = hygiene.get("removed_seller_domain_rows") or []
    missing_summary = "; ".join(row.get("company_name") or "Unknown" for row in missing_rows)
    invalid_summary = "; ".join(
        (
            f"{row.get('company_name') or 'Unknown'} (`{row.get('normalized_domain') or row.get('raw_domain') or ''}`)"
        )
        for row in invalid_rows
    )
    duplicate_summary = "; ".join(
        (
            f"{row.get('company_name') or 'Unknown'} (`{row.get('domain') or ''}`, "
            f"first kept: {row.get('kept_company_name') or 'unknown'})"
        )
        for row in duplicate_rows
    )

    def filter_value(filter_id: str) -> Any:
        return (filters.get(filter_id) or {}).get("value")

    def pass_mark(ok: bool | None) -> str:
        if ok is True:
            return "Pass"
        if ok is False:
            return "Fail"
        return "Not in search row"

    def money_threshold_cell(value: Any, threshold: Any, *, missing_label: str) -> str:
        try:
            ok = float(value) >= float(threshold)
        except (TypeError, ValueError):
            return missing_label
        return f"{fmt_money(value)} >= {fmt_money(threshold)} ({pass_mark(ok)})"

    def employee_cell(row: dict[str, Any]) -> str:
        raw_emp = row.get("employeeCount") or row.get("employees")
        emp_range = row.get("employeesRange")
        try:
            ok = int(raw_emp) >= int(min_employees)
        except (TypeError, ValueError):
            return "Not in search row"
        if emp_range:
            return f"{emp_range} (HG bucket lower bound {raw_emp} >= {min_employees}: {pass_mark(ok)})"
        return f"{raw_emp} >= {min_employees} ({pass_mark(ok)})"

    lines = [
        "# ICP-Compatible Candidate Companies",
        "",
        f"**{len(candidates)} companies matched the ICP filters.**",
        "",
        "This file is intentionally **not a ranking**. It is an audit table of companies that "
        "passed deterministic ICP filters.",
        "",
        "## ICP Thresholds Applied",
        "",
        "| ICP criterion | Threshold used in this run | How they were determined | HG MCP tool / code function |",
        "|---------------|----------------------------|--------------------------|-----------------------------|",
        (
            f"| Revenue floor | >= {fmt_money(filter_value('min_revenue_usd') or min_revenue)} | "
            "You entered this minimum when creating the seller profile (Ideal Customer Profile). | "
            "`search_companies.revenueMin` + row check on `revenue` / `revenueAmount` |"
        ),
        (
            f"| Employee floor | >= {filter_value('min_employees') or min_employees:,} employees | "
            "You entered this minimum when creating the seller profile (Ideal Customer Profile). | "
            "`search_companies.employeesMin` + row check on `employeeCount` |"
        ),
        (
            f"| IT spend floor | >= {fmt_money(filter_value('min_it_spend_usd') or min_it_spend)} | "
            "You entered this minimum when creating the seller profile (Ideal Customer Profile). | "
            "`company_spend` Total IT line (per company in audit table) |"
        ),
        (
            f"| Product / category adjacency | HG category **`{category or 'n/a'}`** required | "
            "The product you sell is mapped to an HG technology category. We pass that category to "
            "`search_companies.technologies` so HG only returns companies that already show activity "
            "in that category (related installs/signals) — not firms from unrelated industries. | "
            "`list_product_categories` + `search_companies.technologies` |"
        ),
        (
            f"| Already uses seller product? | Expected: **No** | "
            "Land motion: companies that already have your HG SKU installed are excluded from the search. | "
            f"`search_companies.excludeTechnologies` → `{product_name}` |"
        ),
        "",
        "## HG Search Arguments",
        "",
        f"- Function: `shortlist_engine.fetch_prospect_universe()` -> HG MCP `search_companies`",
        f"- `revenueMin`: `{attempted.get('revenueMin')}`",
        f"- `employeesMin`: `{attempted.get('employeesMin')}`",
        f"- `technologies`: `{attempted.get('technologies')}`",
        f"- `excludeTechnologies`: `{attempted.get('excludeTechnologies')}`",
        f"- `limit`: `{attempted.get('limit')}`",
        "",
        "## Hygiene / De-duplication",
        "",
        "`After hygiene` means the system applied `shortlist_engine.build_icp_candidate_list()` before "
        "candidate filtering:",
        "",
        "- **Domain field checked:** HG `search_companies.domain` first, then `companyDomain` if present.",
        "- **No usable domain:** HG returned a company row but no usable website/domain. Some `search_companies.companyId` values can arrive in scientific notation, which makes them difficult to reuse as stable MCP identifiers. If no usable domain is available and the id has this format, the agent no longer has a reliable identifier for the next deep calls (`company_firmographic`, `company_spend`, `company_technographic`, `company_intent`).",
        "- **Duplicated domain:** two or more HG rows point to the same normalized domain. The system keeps the first occurrence because we want distinct companies in the candidate list, not several subsidiaries or rows attached to the same corporate website. This is not necessarily the seller/client.",
        "- **Seller domain:** if HG returns the seller's own company domain in the prospect search, it is removed because we do not prospect inside the company that is using the AI agent.",
        "",
        f"- Input companies from HG search: **{stats.get('input_count', 0)}**",
        f"- Removed because domain was not usable: **{hygiene.get('removed_missing_domain', 0)}**",
        "  - Meaning: HG returned a company row, but neither `domain` nor `companyDomain` provided a usable value.",
        "  - Why removed: if no usable domain is available and `companyId` is serialized in scientific notation, the agent has no reliable identifier for the next deep calls (`company_firmographic`, `company_spend`, `company_technographic`, `company_intent`).",
        f"  - Rows removed: {missing_summary or 'none'}.",
        f"- Removed because domain format failed hygiene: **{hygiene.get('removed_invalid_domain', 0)}**",
        "  - Meaning: normalized host looked malformed (invalid labels/TLD), so deep HG company calls are unreliable.",
        "  - Why removed: prevent wasting Step 3 scoring attempts on domains that almost always fail firmographic resolution.",
        f"  - Rows removed: {invalid_summary or 'none'}.",
        f"- Removed because domain was duplicated: **{hygiene.get('removed_duplicate_domain', 0)}**",
        "  - Meaning: HG returned another company row with a domain already seen earlier in the same search response.",
        "  - Why removed: we want distinct companies in the candidate list, not several subsidiaries or rows attached to the same corporate website.",
        f"  - Rows removed: {duplicate_summary or 'none'}.",
        f"- Removed because it was the seller domain: **{hygiene.get('removed_seller_domain', 0)}**",
        "  - Meaning: if HG returns the seller's own company domain in the prospect search, we remove it because we do not prospect inside the company that is using the AI agent.",
        f"- Kept after hygiene: **{stats.get('after_hygiene', 0)}**",
        f"- Final ICP-compatible candidates: **{stats.get('candidate_count', len(candidates))}**",
        "",
    ]

    lines.extend(
        [
            "## Candidate Companies",
            "",
            "Note on employees: when HG returns `employeesRange` like `From 200 to 499`, "
            "`employeeCount = 200` is the **lower bound of the bucket**, not an exact headcount.",
            "",
            "Note on IT spend: Step 2 uses `search_companies` rows only (fast). If IT spend is "
            "not in the search row, the column shows *Not in search row* — the floor is still "
            "enforced when HG returns spend; deep PRS (Step 3) always calls `company_spend`. "
            "Use `--enrich-icp-it-spend` only for a full audit (slow: 1 MCP call per candidate).",
            "",
            "| Domain | Revenue threshold | Employee threshold | IT spend threshold | Category adjacency | Already uses seller product? | Industry |",
            "|--------|-------------------|--------------------|--------------------|--------------------|------------------------------|----------|",
        ]
    )
    for row in candidates[:200]:
        domain = row.get("domain") or row.get("companyDomain") or "—"
        it_missing = "Not in search row (measured in Step 3 if selected for deep PRS)"
        revenue = money_threshold_cell(
            row.get("revenueAmount") or row.get("revenue"),
            min_revenue,
            missing_label="Not in search row",
        )
        employees = employee_cell(row)
        it_spend = money_threshold_cell(
            row.get("itSpend") or row.get("it_spend"),
            min_it_spend,
            missing_label=it_missing,
        )
        category_cell = (
            f"Yes — HG category `{category}` required in search (related tech activity)"
            if category_applied
            else "Not verified in this run (technology filter absent)"
        )
        product_cell = (
            f"No - `{product_name}` excluded by `excludeTechnologies`"
            if product_exclusion_applied
            else "Not verified in this run (exclusion filter absent)"
        )
        industry = row.get("industry") or ""
        lines.append(
            f"| `{domain}` | {revenue} | {employees} | {it_spend} | "
            f"{category_cell} | {product_cell} | {industry} |"
        )
    if len(candidates) > 200:
        lines.append(f"| ... | _{len(candidates) - 200} more_ | | | | | |")
    lines.append("")
    return "\n".join(lines)


def run_pipeline(
    company: str,
    product_index: int = 1,
    prs_count: int = 3,
    search_limit: int = MAX_SEARCH_LIMIT,
    full_profile: bool = False,
    run_name: str | None = None,
    ask_run_name: bool = False,
    sample_seed: int | None = None,
    profile_slug: str | None = None,
    enrich_icp_it_spend: bool = False,
    log_fn: Callable[[str], None] | None = None,
) -> dict[str, Any] | int:
    global _LOG_FN
    previous_log = _LOG_FN
    _LOG_FN = log_fn
    try:
        return _run_pipeline_body(
            company=company,
            product_index=product_index,
            prs_count=prs_count,
            search_limit=search_limit,
            full_profile=full_profile,
            run_name=run_name,
            ask_run_name=ask_run_name,
            sample_seed=sample_seed,
            profile_slug=profile_slug,
            enrich_icp_it_spend=enrich_icp_it_spend,
        )
    finally:
        _LOG_FN = previous_log


def _run_pipeline_body(
    company: str,
    product_index: int = 1,
    prs_count: int = 3,
    search_limit: int = MAX_SEARCH_LIMIT,
    full_profile: bool = False,
    run_name: str | None = None,
    ask_run_name: bool = False,
    sample_seed: int | None = None,
    profile_slug: str | None = None,
    enrich_icp_it_spend: bool = False,
) -> dict[str, Any] | int:
    iteration_dir, iteration_key, iteration_title = allocate_iteration(
        OUTPUTS_ROOT,
        run_name=run_name,
        ask_name=ask_run_name,
    )
    _log(f"Output folder: {iteration_dir.relative_to(ROOT)} ({iteration_title})\n")

    try:
        client = HgMcpClient()
    except HgMcpError as exc:
        _log(f"ERROR: {exc}")
        return 1

    _log("=== PRS Pipeline (3 steps) ===\n")
    _log(f"Company: {company} | Product index: {product_index} | Deep PRS count: {prs_count}\n")

    slug_guess = (profile_slug or company).strip().lower()
    profile_path = PROFILE_DIR / f"seller_profile_{slug_guess}.json"

    _log("--- Step 1/3: ICP Profile configuration from Seller profile ---")
    try:
        if full_profile or not profile_path.is_file():
            _log("  → company_firmographic + vendor catalog + product binding...")
            profile_path, payload = build_seller_profile(client, company, product_index)
        else:
            _log(f"  → Update product binding to #{product_index} in {profile_path.name}...")
            profile_path, payload = update_product_binding_only(
                client, profile_path, product_index
            )
    except HgMcpError as exc:
        _log(f"ERROR Step 1: {exc}")
        return 1

    seller = payload.get("seller_profile") or payload
    selected = seller.get("selected_product") or {}
    binding = selected.get("hg_binding") or {}
    _log(f"  Product: {selected.get('product_name')}")
    _log(f"  HG SKU: {binding.get('hg_product_name')}\n")

    (iteration_dir / "icp_thresholds.json").write_text(
        json.dumps(seller.get("ideal_customer_profile") or {}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _log("--- Step 2/3: ICP candidate filtering (no scoring, no ranking) ---")
    try:
        _log(
            "  → ICP: revenue/employee floors, category signal, "
            "excludeTechnologies (seller SKU not installed)..."
        )
        companies, search_meta = fetch_prospect_universe(client, seller, limit=search_limit)
    except HgMcpError as exc:
        _log(f"ERROR Step 2: {exc}")
        return 1
    (iteration_dir / "prospect_universe.json").write_text(
        json.dumps({"companies": companies, "meta": search_meta}, indent=2) + "\n",
        encoding="utf-8",
    )
    _log(f"  Companies returned: {len(companies)}\n")
    if not companies:
        _log("ERROR: search returned 0 companies.")
        return 1

    candidates, candidate_stats = build_icp_candidate_list(companies, seller)
    if enrich_icp_it_spend:
        _log(
            f"  Enriching IT spend for {len(candidates)} candidates "
            "(1–2 HG MCP calls per company — this can take many minutes)..."
        )
        candidates, it_enrich_meta = enrich_candidates_it_spend(client, candidates)
        candidate_stats["it_spend_enrichment"] = it_enrich_meta
        _log(
            f"  IT spend found for {it_enrich_meta.get('enriched_count', 0)} companies "
            f"({it_enrich_meta.get('from_company_spend', 0)} via company_spend, "
            f"{it_enrich_meta.get('from_firmographic', 0)} via firmographic); "
            f"{it_enrich_meta.get('still_missing', 0)} still missing."
        )
    else:
        candidate_stats["it_spend_enrichment"] = {
            "skipped": True,
            "reason": "Use --enrich-icp-it-spend to fetch company_spend for every ICP row (slow).",
        }
    (iteration_dir / "candidate_companies.json").write_text(
        json.dumps(
            {"stats": candidate_stats, "companies": candidates},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (iteration_dir / "candidate_companies.md").write_text(
        _render_candidate_companies_md(candidates, candidate_stats, seller, search_meta),
        encoding="utf-8",
    )
    _log(f"  {len(candidates)} companies matched the ICP filters.\n")
    if not candidates:
        _log("ERROR: no ICP-compatible candidate companies.")
        return 1

    _log(f"--- Step 3/3: Deep analysis of prospects to score deeply ---")
    sampled_rows, sample_stats = sample_icp_candidates(candidates, prs_count, seed=sample_seed)
    full_pool_rows, _ = sample_icp_candidates(candidates, len(candidates), seed=sample_seed)
    sampled_domains = {
        (row.get("domain") or row.get("companyDomain") or "").lower().strip()
        for row in sampled_rows
    }
    replacement_rows = [
        row
        for row in full_pool_rows
        if (row.get("domain") or row.get("companyDomain") or "").lower().strip() not in sampled_domains
    ]
    candidate_stats["sample"] = sample_stats
    _log(
        f"  Randomly selected {len(sampled_rows)} companies from "
        f"{len(candidates)} ICP-compatible candidates."
    )
    if sample_seed is not None:
        _log(f"  Sample seed: {sample_seed}")
    _log("")

    binding_loaded = _load_binding(seller)
    results = []
    skipped: list[dict[str, Any]] = []
    scored_domains: set[str] = set()
    selected_trace: list[dict[str, Any]] = []
    preflight_stats: dict[str, Any] = {
        "attempted": 0,
        "passed": 0,
        "failed": 0,
    }
    initial_queue = list(sampled_rows)
    queue = initial_queue + replacement_rows

    for idx, row in enumerate(queue, start=1):
        if len(results) >= prs_count:
            break
        domain = row.get("domain") or "?"
        domain_key = str(domain).lower().strip()
        if domain_key in scored_domains:
            continue
        scored_domains.add(domain_key)
        source = "initial_sample" if idx <= len(initial_queue) else "replacement_candidate"
        preflight_stats["attempted"] += 1
        pf = preflight_firmographic(client, row)
        if not pf.get("scorable"):
            preflight_stats["failed"] += 1
            reason = str(pf.get("reason") or "preflight_not_scorable")
            _log(f"  Skipping ({source}): {domain} — preflight failed: {reason}")
            skipped.append(
                {
                    "domain": domain,
                    "reason": f"preflight_failed: {reason}",
                    "selection_source": source,
                }
            )
            continue
        preflight_stats["passed"] += 1
        row_for_scoring = {
            **row,
            "domain": pf.get("canonical_domain") or (row.get("domain") or row.get("companyDomain")),
            "companyDomain": pf.get("canonical_domain") or (row.get("domain") or row.get("companyDomain")),
            "companyName": pf.get("company_name") or row.get("companyName"),
            "_preflight": pf,
        }
        _log(f"  Scoring ({source}): {domain}...")
        try:
            scored = score_prospect(client, row_for_scoring, binding_loaded)
            results.append(scored)
            selected_trace.append(
                {
                    **row,
                    "sample_position": len(selected_trace) + 1,
                    "sample_status": "selected_for_deep_prs",
                    "selection_source": source,
                }
            )
        except Exception as exc:  # noqa: BLE001
            _log(f"    Skipped: {exc}")
            skipped.append({"domain": domain, "reason": str(exc), "selection_source": source})

    if not results:
        _log("ERROR: no prospects scored.")
        return 1
    if len(results) < prs_count:
        _log(
            f"  Warning: requested {prs_count} deep PRS scores but only {len(results)} were scorable "
            f"after trying {len(scored_domains)} candidates."
        )

    sampled_payload_stats = {
        **sample_stats,
        "preflight": preflight_stats,
        "replacement_pool_count": len(replacement_rows),
        "replacement_attempts": max(0, len(scored_domains) - len(initial_queue)),
        "attempted_count": len(scored_domains),
        "scored_count": len(results),
        "skipped_count": len(skipped),
        "final_selected_count": len(selected_trace),
    }
    (iteration_dir / "sampled_prospects.json").write_text(
        json.dumps({"stats": sampled_payload_stats, "prospects": selected_trace}, indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    _log("\n--- Reports: Markdown + JSON ---")
    results.sort(key=lambda r: r.prs, reverse=True)
    for rank, item in enumerate(results, start=1):
        item.rank = rank

    candidate_stats["deep_prs"] = {
        "requested_count": prs_count,
        "sampled_count": len(sampled_rows),
        "preflight": preflight_stats,
        "replacement_pool_count": len(replacement_rows),
        "attempted_count": len(scored_domains),
        "scored_count": len(results),
        "skipped": skipped,
    }

    seller_meta = {
        "slug": slug_guess,
        "company_name": seller.get("company_name"),
        "target_product": selected.get("product_name"),
        "hg_product_name": binding_loaded.get("hg_product_name"),
        "hg_product_id": binding_loaded.get("hg_product_id"),
        "hg_category_name": binding_loaded.get("hg_category_name"),
        "hg_intent_topic_name": binding_loaded.get("hg_intent_topic_name"),
        "iteration": iteration_title,
    }

    paths = write_iteration_reports(
        iteration_dir,
        iteration_title,
        seller_meta,
        seller,
        results,
        profile_path,
        pipeline_meta={
            "iteration_key": iteration_key,
            "candidate_stats": candidate_stats,
            "sample_stats": sample_stats,
        },
        universe_companies=companies,
        shortlist_stats=candidate_stats,
    )

    _log("\n=== Pipeline complete ===\n")
    _log(f"{iteration_title} — Ranking by {PROSPECT_REVENUE_SCORE_NAME}:\n")
    for p in results:
        _log(
            f"  #{p.rank} {p.company_name} — {PROSPECT_REVENUE_SCORE_NAME} {p.prs:.1f} | "
            f"{WEIGHTED_RELIABILITY_LABEL} {reliability_pct(p.reliability_global)}"
        )
    _log(f"\nPrimary report:\n  {paths['executive_summary.md'].relative_to(ROOT)}")
    return {
        "ok": True,
        "iteration_dir": str(iteration_dir),
        "iteration_title": iteration_title,
        "paths": {k: str(v) for k, v in paths.items()},
        "results": [
            {
                "rank": p.rank,
                "company_name": p.company_name,
                "domain": p.domain,
                "prs": round(p.prs, 2),
                "reliability": round(p.reliability_global, 4),
            }
            for p in results
        ],
        "candidate_count": len(candidates),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run 3-step PRS pipeline",
        epilog="Run without flags for interactive prompts (npm run pipeline).",
    )
    parser.add_argument("--company", default=None)
    parser.add_argument("--product-index", type=int, default=None)
    parser.add_argument("--prs-count", type=int, default=None)
    parser.add_argument("--search-limit", type=int, default=MAX_SEARCH_LIMIT)
    parser.add_argument("--sample-seed", type=int, default=None, help="Optional random seed for reproducible demos")
    parser.add_argument("--full-profile", action="store_true")
    parser.add_argument("--run-name", default=None, help="Custom folder under outputs/")
    parser.add_argument(
        "--ask-run-name",
        action="store_true",
        help="Prompt for output folder (redundant if interactive)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="No prompts; defaults: amazon, product 1, 3 prospects, auto iteration folder",
    )
    parser.add_argument(
        "--enrich-icp-it-spend",
        action="store_true",
        help="Fetch company_spend per ICP candidate for audit table (slow; not recommended for live demos)",
    )
    args = parser.parse_args()

    interactive = is_interactive() and not args.non_interactive

    company = args.company
    product_index = args.product_index
    prs_count = args.prs_count
    run_name = args.run_name
    ask_run_name = args.ask_run_name
    profile_slug = None

    if interactive:
        print("=== PRS Pipeline — manual input ===")
        last = load_last_profile_run()
        if last and company is None:
            company = last.get("company_name") or last["company_input"]
            profile_slug = last.get("company_slug")
            if product_index is None:
                product_index = int(last["product_index"])
            print(
                f"\nReusing the last `npm run profile:seller` run:\n"
                f"  {last.get('company_name')} — {last.get('product_name')} "
                f"(product #{product_index})\n"
            )
        else:
            if company is None:
                company = prompt_company()
            slug = company.strip().lower()
            profile_path = PROFILE_DIR / f"seller_profile_{slug}.json"
            if product_index is None:
                if last and last.get("company_slug") == slug:
                    product_index = int(last["product_index"])
                    profile_slug = last.get("company_slug")
                    pname = last.get("product_name") or "—"
                    print(
                        f"\nReusing seller profile product #{product_index} from last `npm run profile:seller` "
                        f"({pname}). Pass `--product-index N` to override.\n"
                    )
                else:
                    product_index = prompt_product_index(profile_path, default=1)
        if prs_count is None:
            prs_count = prompt_prs_count(3)
        if run_name is None and not ask_run_name:
            run_name = prompt_run_folder()
            ask_run_name = False
        elif ask_run_name and run_name is None:
            run_name = prompt_run_name()
    else:
        company = company or "amazon"
        product_index = product_index if product_index is not None else 1
        prs_count = prs_count if prs_count is not None else 3

    if run_name:
        run_name = slugify_run_name(run_name) or None

    result = run_pipeline(
        company=company,
        product_index=product_index,
        prs_count=max(1, min(10, prs_count or 3)),
        search_limit=max(10, min(MAX_SEARCH_LIMIT, args.search_limit)),
        full_profile=args.full_profile,
        run_name=run_name,
        ask_run_name=ask_run_name and run_name is None,
        sample_seed=args.sample_seed,
        profile_slug=profile_slug,
        enrich_icp_it_spend=args.enrich_icp_it_spend,
    )
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main())
