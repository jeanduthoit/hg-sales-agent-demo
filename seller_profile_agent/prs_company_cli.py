#!/usr/bin/env python3
"""Score one prospect company with PRS and write a single {company}_prs.md report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from executive_reports import write_company_prs_report
from hg_client import HgMcpClient, HgMcpError
from last_run_state import load_last_profile_run
from prompt_inputs import is_interactive, prompt_prospect_company
from prospect_preflight import resolve_prospect_firmographic
from prospect_scorer import score_prospect
from sales_insights import build_prospect_card
from score_cli import _load_binding

ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "output" / "seller_profiles"
DEFAULT_OUT_DIR = ROOT / "output" / "prs_reports"


def _resolve_profile_path(profile_arg: str | None, seller_slug: str | None) -> Path:
    if profile_arg:
        path = Path(profile_arg)
        if not path.is_file():
            raise FileNotFoundError(f"Profile not found: {path}")
        return path

    if seller_slug:
        path = PROFILE_DIR / f"seller_profile_{seller_slug.strip().lower()}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Profile not found: {path}")
        return path

    last = load_last_profile_run()
    if last and last.get("company_slug"):
        path = PROFILE_DIR / f"seller_profile_{last['company_slug']}.json"
        if path.is_file():
            return path

    candidates = sorted(
        PROFILE_DIR.glob("seller_profile_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        "No seller profile found. Run `npm run profile:seller` first, or pass --profile or --seller-slug."
    )


def _pick_best_company_row(query: str, companies: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not companies:
        return None
    q = query.strip().lower()

    for row in companies:
        domain = (row.get("domain") or row.get("companyDomain") or "").lower()
        name = (row.get("companyName") or row.get("company_name") or "").lower()
        if domain == q or q in domain:
            return row
        if name == q or q in name:
            return row

    return companies[0]


def resolve_prospect_row(client: HgMcpClient, company_query: str) -> dict[str, Any]:
    """Resolve a company name or domain to a search_companies-style row."""
    query = company_query.strip()
    if not query:
        raise ValueError("Company query is empty")

    looks_like_domain = "." in query and " " not in query

    if looks_like_domain:
        resolved = resolve_prospect_firmographic(
            client,
            {"domain": query, "companyDomain": query},
        )
        if resolved.get("found"):
            firmo = resolved["firmographic"]
            domain = (resolved.get("canonical_domain") or query).lower().strip()
            return {
                "companyName": resolved.get("company_name")
                or firmo.get("name")
                or firmo.get("companyName")
                or query,
                "domain": domain,
                "companyDomain": domain,
                "_preflight": {
                    "firmographic": firmo,
                    "canonical_domain": domain,
                    "search_domain": query,
                    "resolution_method": resolved.get("resolution_method"),
                    "resolution_trace": resolved.get("resolution_trace"),
                },
            }

    data, err = client.call_tool_safe(
        "search_companies",
        {"companyName": query, "limit": 10},
    )
    if err:
        raise HgMcpError(f"search_companies failed for {query!r}: {err}")
    companies = (data or {}).get("companies") or []
    row = _pick_best_company_row(query, companies)
    if not row:
        raise HgMcpError(f"No HG company found for {query!r}")

    domain = (row.get("domain") or row.get("companyDomain") or "").strip()
    if not domain:
        raise HgMcpError(
            f"HG returned {row.get('companyName', query)} but no usable domain for deep PRS."
        )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deep PRS for one prospect and write output/prs_reports/{name}_prs.md",
        epilog=(
            "Examples:\n"
            "  npm run prs\n"
            "  npm run prs -- --company nike.com\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--company",
        default=None,
        help="Prospect domain or name (optional — prompted in the terminal if omitted)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Path to seller_profile.json (default: last npm run profile:seller)",
    )
    parser.add_argument(
        "--seller-slug",
        default=None,
        help="Seller profile slug without prefix, e.g. microsoft → seller_profile_microsoft.json",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help=f"Output directory (default: {DEFAULT_OUT_DIR.relative_to(ROOT)})",
    )
    args = parser.parse_args()

    company_query = (args.company or "").strip()
    if not company_query:
        if not is_interactive():
            print(
                "ERROR: --company is required when stdin is not a terminal.",
                file=sys.stderr,
            )
            return 1
        company_query = prompt_prospect_company()

    try:
        profile_path = _resolve_profile_path(args.profile, args.seller_slug)
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    seller = payload.get("seller_profile") or payload
    binding = _load_binding(seller)
    selected = seller.get("selected_product") or {}

    try:
        client = HgMcpClient()
    except HgMcpError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\nSeller profile: {profile_path.relative_to(ROOT)}")
    print(f"Seller: {seller.get('company_name')} | Product: {selected.get('product_name')}")
    print(f"\nLooking up prospect: {company_query}...")

    try:
        row = resolve_prospect_row(client, company_query)
    except (HgMcpError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    domain = row.get("domain") or row.get("companyDomain")
    print(f"  → {row.get('companyName')} ({domain})")
    print("Scoring (5–8 HG MCP calls)...")

    try:
        prospect = score_prospect(client, row, binding)
    except HgMcpError as exc:
        print(f"ERROR scoring: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR scoring: {exc}", file=sys.stderr)
        return 1

    prospect.rank = 1
    seller_meta = {
        "slug": profile_path.stem.replace("seller_profile_", ""),
        "company_name": seller.get("company_name"),
        "target_product": selected.get("product_name"),
        "hg_product_name": binding.get("hg_product_name"),
        "hg_product_id": binding.get("hg_product_id"),
        "hg_category_name": binding.get("hg_category_name"),
        "hg_intent_topic_name": binding.get("hg_intent_topic_name"),
    }
    card = build_prospect_card(prospect, seller_meta, comparative_bullets=None)

    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT_DIR
    report_path = write_company_prs_report(out_dir, seller_meta, seller, prospect, card)

    print("\nDone.")
    print(f"  PRS: {prospect.prs:.1f}/100 | PRS score reliability: {round(prospect.reliability_global * 100)}%")
    print(f"\nPRS report file:\n  {report_path.resolve()}")
    if prospect.raw_notes:
        for note in prospect.raw_notes[:3]:
            print(f"  Note: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
