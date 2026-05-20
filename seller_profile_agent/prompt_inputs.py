"""Terminal prompts for manual demo runs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def is_interactive() -> bool:
    return sys.stdin.isatty()


def prompt_line(label: str) -> str:
    while True:
        raw = input(f"{label}: ").strip()
        if raw:
            return raw
        print("  (required — please enter a value)")


def prompt_prospect_company() -> str:
    """Ask which prospect to score (domain or company name)."""
    print("\nWhich prospect do you want to score?")
    return prompt_line("Company name or domain")


def prompt_int(label: str, default: int, min_val: int, max_val: int) -> int:
    hint = f"{label} ({min_val}-{max_val}, Enter = {default})"
    while True:
        print(f"{hint}: ", end="", flush=True)
        raw = input().strip()
        if not raw:
            return default
        try:
            value = int(raw)
            if min_val <= value <= max_val:
                return value
        except ValueError:
            pass
        print(f"  Enter an integer between {min_val} and {max_val}.", flush=True)


def list_products_from_profile(profile_path: Path) -> list[dict]:
    if not profile_path.is_file():
        return []
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
        seller = payload.get("seller_profile") or payload
        return seller.get("available_products") or []
    except (json.JSONDecodeError, OSError):
        return []


def prompt_company() -> str:
    print("\n--- Seller ---")
    return prompt_line("Company name")


def _parse_positive_int(raw: str) -> int | None:
    cleaned = raw.strip().replace(",", "").replace("_", "").replace(" ", "")
    if not cleaned:
        return None
    try:
        value = int(cleaned)
        return value if value > 0 else None
    except ValueError:
        return None


def prompt_positive_int(label: str) -> int:
    while True:
        raw = input(f"{label}: ").strip()
        value = _parse_positive_int(raw)
        if value is not None:
            return value
        print("  Enter a positive integer (digits only, e.g. 500000000).", flush=True)


def read_icp_user_floors(profile_path: Path) -> dict[str, int] | None:
    """Load user ICP floors from an existing seller profile, if complete."""
    if not profile_path.is_file():
        return None
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
        seller = payload.get("seller_profile") or payload
        floors = seller.get("icp_user_floors")
        if not isinstance(floors, dict):
            return None
        keys = ("min_revenue_usd", "min_employees", "min_it_spend_usd")
        if not all(k in floors for k in keys):
            return None
        return {k: int(floors[k]) for k in keys}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None


def prompt_icp_floors() -> dict[str, int]:
    print("\n--- Ideal Customer Profile (ICP) criteria (required) ---", flush=True)
    print(
        "Set the minimum thresholds for prospects in your Ideal Customer Profile.",
        flush=True,
    )
    return {
        "min_revenue_usd": prompt_positive_int(
            "Ideal Customer Profile — minimum Revenue Floor in USD"
        ),
        "min_employees": prompt_positive_int(
            "Ideal Customer Profile — minimum Employee floor"
        ),
        "min_it_spend_usd": prompt_positive_int(
            "Ideal Customer Profile — minimum IT spend floor in USD"
        ),
    }


def print_product_line_menu(products: list[dict]) -> None:
    print("\n--- HG technographic product ---", flush=True)
    if not products:
        print("  (no HG catalog products available)", flush=True)
        return
    print("Choose the product sold (type the number, then press Enter):", flush=True)
    for i, p in enumerate(products, start=1):
        name = p.get("product_name") or "?"
        print(f"  {i}. {name}", flush=True)


def _prompt_int_plain(label: str, default: int, min_val: int, max_val: int) -> int:
    while True:
        print(f"{label}: ", end="", flush=True)
        raw = input().strip()
        if not raw:
            return default
        try:
            value = int(raw)
            if min_val <= value <= max_val:
                return value
        except ValueError:
            pass
        print(f"  Enter an integer between {min_val} and {max_val}.", flush=True)


def prompt_product_index(
    profile_path: Path,
    default: int = 1,
    products: list[dict] | None = None,
) -> int:
    listed = products if products is not None else list_products_from_profile(profile_path)
    print_product_line_menu(listed)
    if listed:
        return _prompt_int_plain("Product number", default, 1, len(listed))
    return _prompt_int_plain("Product number", default, 1, 20)


def prompt_prs_count(default: int = 3) -> int:
    print("\n--- Scoring ---")
    return _prompt_int_plain("Number of prospects to score deeply and classify", default, 1, 10)


def prompt_run_folder() -> str | None:
    print("\n--- Output folder ---")
    raw = input("Folder name under outputs/ (empty = automatic iteration): ").strip()
    return raw if raw else None
