#!/usr/bin/env python3
"""Build seller_profile.json — interactive terminal or CLI flags."""

from __future__ import annotations

import argparse
import sys

from hg_client import HgMcpClient, HgMcpError
from cli import _output_slug
from prompt_inputs import (
    is_interactive,
    list_products_from_profile,
    prompt_company,
    prompt_icp_floors,
    prompt_product_index,
    read_icp_user_floors,
)
from last_run_state import save_last_profile_run
from seller_profile_builder import (
    build_seller_profile,
    discover_seller_product_lines,
    update_product_binding_only,
)

ROOT = __import__("pathlib").Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "output" / "seller_profiles"


def _print_hg_search_notice() -> None:
    print(
        "\n  Searching the HG database for this company. This may take 30–90 seconds...",
        flush=True,
    )


def _print_found(company_name: str, domain: str) -> None:
    print(f"  Found: {company_name} ({domain or '—'})", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build seller_profile.json from HG MCP",
        epilog="Run without flags for interactive prompts (npm run profile:seller).",
    )
    parser.add_argument("--company", default=None, help="Seller company name")
    parser.add_argument("--product-index", type=int, default=None, help="Product line number 1..N")
    parser.add_argument("--full", action="store_true", help="Force full profile rebuild")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt; use defaults (amazon, product 1) if flags omitted",
    )
    args = parser.parse_args()

    interactive = is_interactive() and not args.non_interactive

    company = args.company
    product_index = args.product_index
    full = args.full
    company_input = company

    if interactive and company is None:
        company = prompt_company()
        company_input = company

    company = company or "amazon"
    slug = company.strip().lower()
    profile_path = PROFILE_DIR / f"seller_profile_{slug}.json"

    try:
        client = HgMcpClient()
    except HgMcpError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    prefetch: dict | None = None
    found_printed = False
    product_lines: list[dict] | None = None
    if interactive and product_index is None:
        product_lines = list_products_from_profile(profile_path)
        if not product_lines:
            _print_hg_search_notice()
            try:
                prefetch = discover_seller_product_lines(client, company)
                company = prefetch["company_name"]
                domain = prefetch["domain"]
                product_lines = prefetch["products"]
                slug = _output_slug(company, domain)
                profile_path = PROFILE_DIR / f"seller_profile_{slug}.json"
                _print_found(company, domain)
                found_printed = True
            except HgMcpError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1

    # ICP floors: mandatory user input on every interactive profile:seller run.
    stored_floors = read_icp_user_floors(profile_path)
    if interactive:
        icp_floors = prompt_icp_floors()
    else:
        icp_floors = stored_floors  # non-interactive: reuse profile or formula defaults in builder

    if interactive and product_index is None:
        product_index = prompt_product_index(profile_path, default=1, products=product_lines)
    elif product_index is None:
        product_index = 1

    floors_changed = icp_floors is not None and icp_floors != stored_floors
    needs_full_build = full or not profile_path.is_file() or stored_floors is None or floors_changed

    try:
        if needs_full_build:
            if interactive and prefetch is None and not profile_path.is_file():
                _print_hg_search_notice()
            path, payload = build_seller_profile(
                client, company, product_index, prefetch=prefetch, icp_floors=icp_floors
            )
            if interactive and not found_printed:
                seller_tmp = payload.get("seller_profile") or payload
                _print_found(
                    str(seller_tmp.get("company_name") or company),
                    str(seller_tmp.get("domain") or ""),
                )
        else:
            path, payload = update_product_binding_only(
                client, profile_path, product_index, icp_floors=icp_floors
            )
    except HgMcpError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    seller = payload.get("seller_profile") or payload
    sel = seller.get("selected_product") or {}
    binding = sel.get("hg_binding") or {}

    product_sold = binding.get("hg_product_name") or sel.get("product_name")

    print(f"\nFile: {path.relative_to(ROOT)}")
    print(f"  Company: {seller.get('company_name')}")
    print(f"  Product sold: {product_sold or '—'}")

    save_last_profile_run(
        company_input=str(company_input or company),
        company_slug=slug,
        product_index=product_index,
        company_name=str(seller.get("company_name") or company),
        product_name=str(product_sold or ""),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
