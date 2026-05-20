#!/usr/bin/env python3
"""Interactive CLI: build a seller profile JSON from HG Insights data."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from company_resolver import (
    KNOWN_DOMAINS,
    format_employee_range,
    format_revenue_range,
    resolve_company,
)
from hg_client import HgMcpClient, HgMcpError
from methodology_binding import enrich_seller_profile_for_methodology
from product_discovery import discover_products

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output" / "seller_profiles"


def _ask(label: str) -> str:
    print(label)
    return input("> ").strip()


def _output_slug(company_input: str, domain: str) -> str:
    key = company_input.strip().lower()
    if key in KNOWN_DOMAINS:
        return key
    if domain:
        return domain.split(".")[0].lower()
    slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return slug or "company"


def _fetch_technologies(client: HgMcpClient, domain: str) -> tuple[list[str], dict]:
    try:
        tech = client.call_tool(
            "company_technographic",
            {"companyDomain": domain, "limit": 40},
        )
    except HgMcpError:
        return [], {}
    products = tech.get("products") or tech.get("installs") or []
    names: list[str] = []
    for item in products:
        name = item.get("productName") or item.get("name") or item.get("product_name")
        if name and name not in names:
            names.append(name)
    return names[:30], tech


def _build_business_description(firmo: dict) -> str:
    parts: list[str] = []
    name = firmo.get("companyName") or firmo.get("name")
    industry = firmo.get("industry") or firmo.get("industryName")
    country = firmo.get("country") or firmo.get("hqCountry")
    if name:
        parts.append(f"{name} is a company")
    if industry:
        parts.append(f"operating in the {industry} industry")
    if country:
        parts.append(f"headquartered in {country}")
    if not parts:
        return "None"
    sentence = " ".join(parts) + "."
    it_spend = firmo.get("itSpend") or firmo.get("it_spend")
    if it_spend:
        try:
            spend = float(it_spend)
            if spend > 0:
                sentence += f" HG reports estimated IT spend of approximately ${spend:,.0f}."
        except (TypeError, ValueError):
            pass
    return sentence


def _collect_missing(firmo: dict, technologies: list[str]) -> list[str]:
    missing: list[str] = []
    checks = [
        ("industry", firmo.get("industry") or firmo.get("industryName")),
        ("revenue", firmo.get("revenue") or firmo.get("revenueAmount")),
        ("employee_count", firmo.get("employeeCount") or firmo.get("employees")),
        (
            "hg_company_id",
            firmo.get("metadata", {}).get("hginsights_id")
            if isinstance(firmo.get("metadata"), dict)
            else firmo.get("hginsights_id"),
        ),
        ("country", firmo.get("country") or firmo.get("hqCountry")),
        ("technologies_detected", technologies),
    ]
    for field, value in checks:
        if value is None or value == "" or value == []:
            missing.append(field)
    return missing


def main() -> int:
    company_input = _ask("What company do you work for?")
    if not company_input:
        print("Error: company name cannot be empty.")
        return 1

    try:
        client = HgMcpClient()
    except HgMcpError as exc:
        print(f"Configuration error: {exc}")
        return 1

    print("\nLooking up company in HG Insights...\n")
    try:
        firmo = resolve_company(client, company_input)
    except HgMcpError as exc:
        print(f"HG Insights error: {exc}")
        return 1

    if not firmo or not firmo.get("found"):
        print("Company not found in the HG Insights database.")
        return 1

    domain = firmo.get("_resolved_domain") or firmo.get("domain") or ""
    company_name = firmo.get("companyName") or firmo.get("name") or company_input
    metadata = firmo.get("metadata") if isinstance(firmo.get("metadata"), dict) else {}
    hg_id = metadata.get("hginsights_id") or firmo.get("hginsights_id") or firmo.get("hgId")

    industry = firmo.get("industry") or firmo.get("industryName")
    revenue = firmo.get("revenue") or firmo.get("revenueAmount")
    employees = firmo.get("employeeCount") or firmo.get("employees")

    print(f"Found: {company_name}\n")

    technologies, tech_raw = _fetch_technologies(client, domain) if domain else ([], {})

    try:
        products, vendor_summary = discover_products(
            client, company_name, industry, technologies, domain=domain
        )
    except HgMcpError as exc:
        print(f"HG Insights error: {exc}")
        return 1

    if not products:
        print("No sellable products could be derived from HG data.")
        return 1

    print("Possible products/services:")
    for p in products:
        print(f"{p['id']}. {p['product_name']}")
    print()

    while True:
        choice = _ask("Select a product number:")
        if choice.isdigit() and 1 <= int(choice) <= len(products):
            selected = products[int(choice) - 1]
            break
        print(f"Invalid choice. Enter a number from 1 to {len(products)}.\n")

    print("\nResolving PRS methodology bindings (HG product, category, intent)...\n")

    try:
        hg_binding, prs_methodology, ideal_customer_profile = enrich_seller_profile_for_methodology(
            client, selected, company_name, domain, vendor_summary, firmo
        )
    except HgMcpError as exc:
        print(f"Warning: methodology binding partial ({exc})")
        hg_binding = {
            "binding_confidence": "low",
            "binding_notes": [str(exc)],
        }
        from methodology_binding import build_ideal_customer_profile, build_prs_methodology_block

        prs_methodology = build_prs_methodology_block(hg_binding)
        ideal_customer_profile = build_ideal_customer_profile(firmo, hg_binding, selected)

    print("Generating seller profile...\n")

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    missing = _collect_missing(firmo, technologies)
    if hg_binding.get("binding_confidence") == "low":
        missing.append("hg_product_binding")
    if not hg_binding.get("hg_category_name"):
        missing.append("hg_category_name")
    if not hg_binding.get("hg_intent_topic_name"):
        missing.append("hg_intent_topic_name")

    profile = {
        "seller_profile": {
            "company_name": company_name,
            "company_found_in_hg": True,
            "hg_company_id": hg_id or "None",
            "industry": industry or "None",
            "company_size": format_employee_range(employees) or "None",
            "revenue_range": format_revenue_range(revenue) or "None",
            "employee_range": format_employee_range(employees) or "None",
            "technologies_detected": technologies,
            "business_description": _build_business_description(firmo),
            "available_products": products,
            "selected_product": {
                "product_name": selected["product_name"],
                "product_category": selected["product_category"],
                "why_this_product_makes_sense": selected["reasoning"],
                "source_type": selected.get("source_type"),
                "hg_binding": hg_binding,
            },
            "prs_methodology": prs_methodology,
            "ideal_customer_profile": ideal_customer_profile,
            "raw_hg_data_used": {
                "resolved_domain": domain,
                "firmographic": firmo,
                "technographic_summary": {
                    "product_count": len(technologies),
                    "sample_products": technologies[:10],
                },
                "vendor_catalog_summary": vendor_summary,
            },
            "missing_data": missing,
            "created_at": created_at,
        }
    }

    if tech_raw:
        profile["seller_profile"]["raw_hg_data_used"]["technographic_raw"] = tech_raw

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = _output_slug(company_input, domain)
    out_file = OUTPUT_DIR / f"seller_profile_{slug}.json"
    out_file.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    relative_path = out_file.relative_to(ROOT)
    print("Seller profile saved to:")
    print(relative_path)
    print("\nNext step — score prospects:")
    print("  npm run score")
    return 0


if __name__ == "__main__":
    sys.exit(main())
