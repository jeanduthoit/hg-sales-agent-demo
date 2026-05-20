"""Build sellable product list (max 20) from HG vendor catalog + inference."""

from __future__ import annotations

import re
from typing import Any

from hg_client import HgMcpClient

MAX_PRODUCTS = 20

# Map HG/AWS-style product names into customer-facing product lines.
PRODUCT_LINE_RULES: list[tuple[str, str, str]] = [
    (r"\b(ec2|elastic compute|compute)\b", "Cloud computing", "Compute instances and elastic capacity"),
    (r"\b(s3|simple storage|object storage|glacier)\b", "Cloud storage", "Object and archival storage"),
    (r"\b(redshift|data warehouse|snowflake competitor)\b", "Data warehouse", "Analytics data warehouse"),
    (r"\b(rds|relational database|aurora|dynamodb|database)\b", "Managed databases", "Relational and NoSQL databases"),
    (r"\b(lambda|serverless|fargate|ecs|eks|kubernetes)\b", "Serverless & containers", "Serverless and container platforms"),
    (r"\b(sagemaker|machine learning|ai/|bedrock|comprehend|rekognition)\b", "AI/ML infrastructure", "ML training, inference, and AI services"),
    (r"\b(cloudfront|cdn|content delivery)\b", "CDN & edge delivery", "Global content delivery"),
    (r"\b(vpc|network|direct connect|privatelink|route 53|dns)\b", "Cloud networking", "VPC, DNS, and private connectivity"),
    (r"\b(iam|identity|cognito|directory|sso|mfa|security hub|guardduty|waf|shield|kms)\b", "Cybersecurity & identity", "Identity, encryption, and threat protection"),
    (r"\b(cloudwatch|monitoring|x-ray|observability)\b", "Observability", "Monitoring, logging, and tracing"),
    (r"\b(backup|disaster recovery|dr)\b", "Backup & disaster recovery", "Backup and recovery services"),
    (r"\b(data pipeline|glue|etl|kinesis|streaming|analytics)\b", "Data integration & analytics", "ETL, streaming, and analytics pipelines"),
    (r"\b(contact center|connect)\b", "Contact center", "Cloud contact center software"),
    (r"\b(marketplace|fulfillment|fba|associates|advertising)\b", "E-commerce & marketplace", "Marketplace, ads, and fulfillment"),
    (r"\b(workspaces|desktop|virtual desktop)\b", "Virtual desktop", "Cloud desktop infrastructure"),
    (r"\b(email|ses|communication)\b", "Business communication", "Email and messaging APIs"),
]

# General business inference when HG vendor catalog is thin (clearly labeled).
GENERAL_INFERENCE_BY_INDUSTRY: dict[str, list[tuple[str, str, str]]] = {
    "travel": [
        ("Vacation rental marketplace", "Travel marketplace", "Core two-sided marketplace for hosts and guests"),
        ("Host management tools", "Hospitality SaaS", "Pricing, calendar, and listing management for hosts"),
        ("Experiences & activities booking", "Travel experiences", "Bookable tours and local experiences"),
        ("Travel insurance partnerships", "Travel fintech", "Insurance and protection products for bookings"),
        ("Corporate travel solutions", "B2B travel", "Managed travel for business customers"),
    ],
    "retail": [
        ("Online marketplace platform", "E-commerce", "Third-party seller marketplace"),
        ("Fulfillment & logistics services", "Supply chain", "Warehousing and last-mile delivery"),
        ("Advertising & sponsored listings", "MarTech", "Retail media and performance ads"),
        ("Subscription & loyalty programs", "Customer engagement", "Recurring revenue and retention"),
    ],
    "software": [
        ("Enterprise SaaS platform", "Enterprise software", "Core licensed or subscription software"),
        ("Professional services & implementation", "Services", "Deployment, integration, and support"),
        ("Developer APIs & SDKs", "Platform", "APIs for partners and integrators"),
    ],
}

# Extra vendor names to query for well-known conglomerates.
EXTRA_VENDORS: dict[str, list[str]] = {
    "amazon": ["Amazon Web Services", "Amazon"],
    "microsoft": ["Microsoft", "Microsoft Azure"],
    "google": ["Google", "Google Cloud"],
    "oracle": ["Oracle"],
    "ibm": ["IBM"],
}


def _classify_product_line(product_name: str) -> tuple[str, str] | None:
    name = product_name.lower()
    for pattern, line_name, description in PRODUCT_LINE_RULES:
        if re.search(pattern, name, re.IGNORECASE):
            return line_name, description
    return None


def _industry_key(industry: str | None) -> str | None:
    if not industry:
        return None
    low = industry.lower()
    if "travel" in low or "hospitality" in low or "leisure" in low:
        return "travel"
    if "retail" in low or "commerce" in low:
        return "retail"
    if "software" in low or "technology" in low or "information" in low:
        return "software"
    return None


def _fetch_vendor_products(client: HgMcpClient, vendor_name: str) -> list[dict[str, Any]]:
    data = client.call_tool("get_vendor_information", {"vendorName": vendor_name})
    vendors = data.get("vendors") or []
    products: list[dict[str, Any]] = []
    for vendor in vendors:
        for product in vendor.get("products") or []:
            products.append(
                {
                    "product_name": product.get("name") or product.get("productName"),
                    "vendor_name": vendor.get("name") or vendor_name,
                    "product_id": product.get("id") or product.get("productId"),
                }
            )
    return products


def _aggregate_hg_products(
    raw_products: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Collapse many HG SKUs into sellable lines; aggregated lines rank above raw SKUs."""
    lines: dict[str, dict[str, Any]] = {}
    singles: dict[str, dict[str, Any]] = {}

    for item in raw_products:
        name = (item.get("product_name") or "").strip()
        if not name:
            continue
        classified = _classify_product_line(name)
        if classified:
            line_name, line_desc = classified
            entry = lines.setdefault(
                line_name,
                {
                    "product_name": line_name,
                    "product_category": line_name,
                    "reasoning": (
                        f"Derived from HG vendor catalog entries such as '{name}'. "
                        f"{line_desc}."
                    ),
                    "source_type": "HG data",
                    "hg_examples": [],
                },
            )
            examples = entry["hg_examples"]
            if name not in examples and len(examples) < 5:
                examples.append(name)
        else:
            key = name[:80]
            if key not in singles:
                singles[key] = {
                    "product_name": name,
                    "product_category": "HG catalog product",
                    "reasoning": f"Listed in HG vendor catalog as '{name}'.",
                    "source_type": "HG data",
                    "hg_examples": [name],
                }

    aggregated = sorted(
        lines.values(),
        key=lambda entry: len(entry.get("hg_examples") or []),
        reverse=True,
    )

    result: list[dict[str, str]] = []
    for entry in aggregated + list(singles.values()):
        examples = entry.pop("hg_examples", [])
        if len(examples) > 1 and "Examples:" not in entry["reasoning"]:
            entry["reasoning"] += f" Examples: {', '.join(examples[:3])}."
        result.append(
            {
                "product_name": entry["product_name"],
                "product_category": entry["product_category"],
                "reasoning": entry["reasoning"],
                "source_type": entry["source_type"],
            }
        )
        if len(result) >= MAX_PRODUCTS:
            break
    return result


def _infer_from_hg_context(
    company_name: str,
    industry: str | None,
    vendor_summary: dict[str, Any],
) -> list[dict[str, str]]:
    """Products inferred from HG firmographics and vendor catalog coverage (not install data)."""
    suggestions: list[dict[str, str]] = []
    catalog_count = vendor_summary.get("catalog_product_count") or 0

    if industry and "financial" in industry.lower():
        suggestions.append(
            {
                "product_name": "Financial data & risk analytics",
                "product_category": "FinTech",
                "reasoning": (
                    f"Industry '{industry}' from HG firmographics suggests regulated "
                    "financial analytics offerings."
                ),
                "source_type": "inferred from HG data",
            }
        )

    if catalog_count > 50 and industry and "retail" in industry.lower():
        suggestions.append(
            {
                "product_name": "Retail media & advertising platform",
                "product_category": "MarTech",
                "reasoning": (
                    f"HG lists {catalog_count} catalog products for {company_name} in retail; "
                    "large retailers commonly monetize traffic via retail media."
                ),
                "source_type": "inferred from HG data",
            }
        )

    return suggestions


def _general_business_inference(
    company_name: str,
    industry: str | None,
) -> list[dict[str, str]]:
    key = _industry_key(industry)
    templates = GENERAL_INFERENCE_BY_INDUSTRY.get(key, [])
    results: list[dict[str, str]] = []
    for product_name, category, reasoning in templates:
        results.append(
            {
                "product_name": product_name,
                "product_category": category,
                "reasoning": (
                    f"{reasoning} Inferred from public business model of {company_name} "
                    f"(industry: {industry or 'unknown'}); not present as a full HG vendor catalog."
                ),
                "source_type": "general business inference",
            }
        )
    return results


def discover_products(
    client: HgMcpClient,
    company_name: str,
    industry: str | None,
    technologies: list[str],
    domain: str | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """
    Return (products with ids 1..n, raw_hg_vendor_payload_summary).
    """
    raw_summary: dict[str, Any] = {"vendors_queried": [], "catalog_product_count": 0}

    vendor_names = _resolve_vendor_names(company_name, domain)

    all_catalog: list[dict[str, Any]] = []
    for vendor in vendor_names:
        try:
            products = _fetch_vendor_products(client, vendor)
            raw_summary["vendors_queried"].append(
                {"vendor_name": vendor, "product_count": len(products)}
            )
            all_catalog.extend(products)
        except Exception as exc:  # noqa: BLE001 — demo CLI keeps going
            raw_summary["vendors_queried"].append(
                {"vendor_name": vendor, "error": str(exc)}
            )

    raw_summary["catalog_product_count"] = len(all_catalog)

    merged: list[dict[str, str]] = []
    seen_names: set[str] = set()

    def add_unique(items: list[dict[str, str]]) -> None:
        for item in items:
            key = item["product_name"].lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            merged.append(item)
            if len(merged) >= MAX_PRODUCTS:
                return

    add_unique(_aggregate_hg_products(all_catalog))
    if len(merged) < MAX_PRODUCTS:
        add_unique(_infer_from_hg_context(company_name, industry, raw_summary))
    if len(merged) < MAX_PRODUCTS:
        add_unique(_general_business_inference(company_name, industry))

    # Assign numeric ids for terminal selection
    numbered: list[dict[str, Any]] = []
    for idx, product in enumerate(merged[:MAX_PRODUCTS], start=1):
        numbered.append({"id": idx, **product})

    return numbered, raw_summary


def _resolve_vendor_names(company_name: str, domain: str | None) -> list[str]:
    slug = re.sub(r"[^a-z0-9]+", "", company_name.lower())
    domain_root = (domain or "").split(".")[0].lower()
    if domain_root in EXTRA_VENDORS:
        return EXTRA_VENDORS[domain_root]
    if slug in EXTRA_VENDORS:
        return EXTRA_VENDORS[slug]
    return [company_name]


def discover_hg_catalog_products(
    client: HgMcpClient,
    company_name: str,
    industry: str | None,
    technologies: list[str],
    domain: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Return numbered HG vendor-catalog SKUs only (no aggregation, no business inference).
    Used for terminal selection in profile:seller.
    """
    del industry, technologies  # reserved for future ranking signals

    raw_summary: dict[str, Any] = {"vendors_queried": [], "catalog_product_count": 0}
    vendor_names = _resolve_vendor_names(company_name, domain)

    all_catalog: list[dict[str, Any]] = []
    for vendor in vendor_names:
        try:
            products = _fetch_vendor_products(client, vendor)
            raw_summary["vendors_queried"].append(
                {"vendor_name": vendor, "product_count": len(products)}
            )
            all_catalog.extend(products)
        except Exception as exc:  # noqa: BLE001 — demo CLI keeps going
            raw_summary["vendors_queried"].append(
                {"vendor_name": vendor, "error": str(exc)}
            )

    raw_summary["catalog_product_count"] = len(all_catalog)

    seen: set[str] = set()
    skus: list[dict[str, Any]] = []
    for item in sorted(
        all_catalog,
        key=lambda row: (row.get("product_name") or "").lower(),
    ):
        name = (item.get("product_name") or "").strip()
        if not name:
            continue
        pid = item.get("product_id")
        dedupe_key = f"id:{pid}" if pid else f"name:{name.lower()}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        vendor_name = item.get("vendor_name") or company_name
        skus.append(
            {
                "product_name": name,
                "hg_product_id": str(pid) if pid else None,
                "product_category": "HG technographic product",
                "reasoning": f"HG vendor catalog SKU ({vendor_name}).",
                "source_type": "HG catalog SKU",
                "vendor_name": vendor_name,
            }
        )
        if len(skus) >= MAX_PRODUCTS:
            break

    numbered: list[dict[str, Any]] = []
    for idx, product in enumerate(skus, start=1):
        numbered.append({"id": idx, **product})

    return numbered, raw_summary
