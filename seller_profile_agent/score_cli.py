#!/usr/bin/env python3
"""Score random prospects using seller_profile.json and export PRS Markdown reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from hg_client import HgMcpClient, HgMcpError
from executive_reports import write_iteration_reports
from iteration_manager import allocate_iteration
from report_format import reliability_pct
from prospect_scorer import fetch_random_prospects, score_prospect

ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "output" / "seller_profiles"
OUTPUT_DIR = ROOT / "outputs"


def _ask(label: str, default: str = "") -> str:
    if default:
        print(f"{label} [{default}]")
    else:
        print(label)
    value = input("> ").strip()
    return value or default


def _latest_profile() -> Path | None:
    files = sorted(PROFILE_DIR.glob("seller_profile_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _load_binding(seller: dict) -> dict:
    selected = seller.get("selected_product") or {}
    binding = dict(selected.get("hg_binding") or {})
    if not binding.get("hg_product_name"):
        binding["hg_product_name"] = selected.get("product_name")
    if not binding.get("hg_category_name"):
        binding["hg_category_name"] = selected.get("product_category")
    if binding.get("hg_competitor_products") is None:
        binding["hg_competitor_products"] = []
    return binding


def main() -> int:
    print("=== PRS Prospect Scoring ===\n")

    profile_path = _latest_profile()
    if not profile_path:
        print("Error: no seller profile found. Run npm run start first.")
        return 1

    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading profile: {exc}")
        return 1

    seller = payload.get("seller_profile") or payload
    binding = _load_binding(seller)
    selected = seller.get("selected_product") or {}

    count_raw = _ask("How many prospects do you want to evaluate?", "5")
    try:
        count = max(1, min(20, int(count_raw)))
    except ValueError:
        print("Invalid number. Using 5.")
        count = 5

    print(f"\nLoaded seller profile (latest): {profile_path.name}")
    print(f"Seller: {seller.get('company_name')}")
    print(f"Target product: {selected.get('product_name')}")
    print(f"HG binding confidence: {binding.get('binding_confidence', 'unknown')}")
    if binding.get("binding_notes"):
        for note in binding["binding_notes"]:
            print(f"  Note: {note}")

    try:
        client = HgMcpClient()
    except HgMcpError as exc:
        print(f"Configuration error: {exc}")
        return 1

    print(f"\nFetching {count} random prospects from HG Insights...")
    try:
        prospects = fetch_random_prospects(client, count)
    except HgMcpError as exc:
        print(f"HG Insights error: {exc}")
        return 1

    if len(prospects) < count:
        print(f"Warning: only {len(prospects)} prospects retrieved.")

    results = []
    for idx, company in enumerate(prospects, start=1):
        domain = company.get("domain") or company.get("companyDomain") or "?"
        print(f"  Scoring {idx}/{len(prospects)}: {domain}...")
        try:
            scored = score_prospect(client, company, binding)
            results.append(scored)
            if scored.raw_notes:
                for note in scored.raw_notes[:2]:
                    print(f"    Warning: {note}")
        except Exception as exc:  # noqa: BLE001 — keep batch running on single prospect failure
            print(f"    Skipped ({exc})")

    if not results:
        print("No prospects scored.")
        return 1

    results.sort(key=lambda r: r.prs, reverse=True)
    for rank, item in enumerate(results, start=1):
        item.rank = rank

    seller_meta = {
        "slug": profile_path.stem.replace("seller_profile_", ""),
        "company_name": seller.get("company_name"),
        "target_product": selected.get("product_name"),
        "hg_product_name": binding.get("hg_product_name"),
        "hg_product_id": binding.get("hg_product_id"),
        "hg_category_name": binding.get("hg_category_name"),
        "hg_intent_topic_name": binding.get("hg_intent_topic_name"),
    }

    iteration_dir, _, iteration_title = allocate_iteration(OUTPUT_DIR)
    paths = write_iteration_reports(
        iteration_dir, iteration_title, seller_meta, seller, results, profile_path
    )

    print("\nScoring complete.\n")
    print(f"Iteration: {iteration_title}")
    print("Executive report:")
    print(paths["executive_summary.md"].relative_to(ROOT))
    print("Technical appendix:")
    print(paths["technical_scoring.md"].relative_to(ROOT))
    print("\nTop 3:")
    for p in results[:3]:
        print(
            f"  #{p.rank} {p.company_name} — PRS {p.prs:.1f} "
            f"(Reliability {reliability_pct(p.reliability_global)})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
