"""Build or update seller_profile.json (non-interactive)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli import (
    OUTPUT_DIR,
    _build_business_description,
    _collect_missing,
    _fetch_technologies,
    _output_slug,
)
from company_resolver import (
    format_employee_range,
    format_revenue_range,
    resolution_hint,
    resolve_company,
)
from hg_client import HgMcpClient, HgMcpError
from methodology_binding import (
    build_ideal_customer_profile,
    build_prs_methodology_block,
    enrich_seller_profile_for_methodology,
)
from product_discovery import discover_hg_catalog_products


def _write_profile_sidecars(profile_path: Path, seller: dict[str, Any]) -> None:
    slug = profile_path.stem.replace("seller_profile_", "")
    profile_path.with_name(f"icp_thresholds_{slug}.json").write_text(
        json.dumps(seller.get("ideal_customer_profile") or {}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def discover_seller_product_lines(
    client: HgMcpClient,
    company_input: str,
) -> dict[str, Any]:
    """
    Resolve company in HG and derive sellable product lines (no file write).
    Returns a prefetch bundle reusable by build_seller_profile to avoid duplicate MCP calls.
    """
    firmo = resolve_company(client, company_input)
    if not firmo or not firmo.get("found"):
        raise HgMcpError(
            f"Company not found in HG: {company_input}. {resolution_hint(company_input)}"
        )

    domain = firmo.get("_resolved_domain") or firmo.get("domain") or ""
    company_name = firmo.get("companyName") or firmo.get("name") or company_input
    industry = firmo.get("industry") or firmo.get("industryName")
    technologies, tech_raw = _fetch_technologies(client, domain) if domain else ([], {})
    products, vendor_summary = discover_hg_catalog_products(
        client, company_name, industry, technologies, domain=domain
    )
    if not products:
        raise HgMcpError(
            "No HG technographic products found for this vendor. "
            "Try a B2B software company with an HG product catalog."
        )
    return {
        "firmo": firmo,
        "domain": domain,
        "company_name": company_name,
        "products": products,
        "vendor_summary": vendor_summary,
        "technologies": technologies,
        "tech_raw": tech_raw,
    }


def build_seller_profile(
    client: HgMcpClient,
    company_input: str,
    product_index: int = 1,
    prefetch: dict[str, Any] | None = None,
    icp_floors: dict[str, int] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Full profile build: firmographic, catalog, technographic, binding."""
    if prefetch:
        firmo = prefetch["firmo"]
        domain = prefetch["domain"]
        company_name = prefetch["company_name"]
        products = prefetch["products"]
        vendor_summary = prefetch["vendor_summary"]
        technologies = prefetch["technologies"]
        tech_raw = prefetch.get("tech_raw") or {}
    else:
        firmo = resolve_company(client, company_input)
        if not firmo or not firmo.get("found"):
            raise HgMcpError(
                f"Company not found in HG: {company_input}. {resolution_hint(company_input)}"
            )

        domain = firmo.get("_resolved_domain") or firmo.get("domain") or ""
        company_name = firmo.get("companyName") or firmo.get("name") or company_input
        industry = firmo.get("industry") or firmo.get("industryName")
        technologies, tech_raw = _fetch_technologies(client, domain) if domain else ([], {})
        products, vendor_summary = discover_hg_catalog_products(
            client, company_name, industry, technologies, domain=domain
        )
        if not products:
            raise HgMcpError(
                "No HG technographic products found for this vendor. "
                "Try a B2B software company with an HG product catalog."
            )

    metadata = firmo.get("metadata") if isinstance(firmo.get("metadata"), dict) else {}
    hg_id = metadata.get("hginsights_id") or firmo.get("hginsights_id") or firmo.get("hgId")
    industry = firmo.get("industry") or firmo.get("industryName")
    revenue = firmo.get("revenue") or firmo.get("revenueAmount")
    employees = firmo.get("employeeCount") or firmo.get("employees")

    if product_index < 1 or product_index > len(products):
        raise HgMcpError(f"product_index must be 1..{len(products)}")
    selected = products[product_index - 1]

    try:
        hg_binding, prs_methodology, ideal_customer_profile = enrich_seller_profile_for_methodology(
            client, selected, company_name, domain, vendor_summary, firmo, icp_floors
        )
    except HgMcpError as exc:
        hg_binding = {"binding_confidence": "low", "binding_notes": [str(exc)]}
        prs_methodology = build_prs_methodology_block(hg_binding)
        ideal_customer_profile = build_ideal_customer_profile(
            firmo, hg_binding, selected, icp_floors
        )

    missing = _collect_missing(firmo, technologies)
    if hg_binding.get("binding_confidence") == "low":
        missing.append("hg_product_binding")

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
                "hg_product_id": selected.get("hg_product_id"),
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
            "icp_user_floors": icp_floors,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    }
    if tech_raw:
        profile["seller_profile"]["raw_hg_data_used"]["technographic_raw"] = tech_raw

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = _output_slug(company_input, domain)
    out_file = OUTPUT_DIR / f"seller_profile_{slug}.json"
    out_file.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_profile_sidecars(out_file, profile["seller_profile"])
    return out_file, profile


def update_product_binding_only(
    client: HgMcpClient,
    profile_path: Path,
    product_index: int,
    icp_floors: dict[str, int] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Re-bind HG product/category/intent without re-fetching firmographic or catalog."""
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    seller = payload.get("seller_profile") or payload
    products = seller.get("available_products") or []
    if product_index < 1 or product_index > len(products):
        raise HgMcpError(f"product_index must be 1..{len(products)}")

    selected = products[product_index - 1]
    raw = seller.get("raw_hg_data_used") or {}
    firmo = raw.get("firmographic") or {}
    domain = raw.get("resolved_domain") or ""
    company_name = seller.get("company_name") or ""
    vendor_summary = raw.get("vendor_catalog_summary") or {}

    floors = icp_floors if icp_floors is not None else seller.get("icp_user_floors")
    hg_binding, prs_methodology, ideal_customer_profile = enrich_seller_profile_for_methodology(
        client, selected, company_name, domain, vendor_summary, firmo, floors
    )

    seller["selected_product"] = {
        "product_name": selected["product_name"],
        "product_category": selected["product_category"],
        "why_this_product_makes_sense": selected["reasoning"],
        "source_type": selected.get("source_type"),
        "hg_product_id": selected.get("hg_product_id"),
        "hg_binding": hg_binding,
    }
    seller["prs_methodology"] = prs_methodology
    seller["ideal_customer_profile"] = ideal_customer_profile
    if floors:
        seller["icp_user_floors"] = floors
    seller["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload["seller_profile"] = seller

    profile_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_profile_sidecars(profile_path, seller)
    return profile_path, payload
