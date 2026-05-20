"""Parse numeric values from HG firmographic and search fields."""

from __future__ import annotations

import re
from typing import Any


def parse_hg_numeric(value: Any) -> float | None:
    """
    Convert HG revenue, employee, or spend fields to a positive number.
    Handles plain numbers and range strings such as 'From $10,000,000 to $49,999,999'.
    Uses the lower bound when a range is present (consistent with ICP search buckets).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number > 0 else None

    text = str(value).strip()
    if not text:
        return None

    cleaned = text.replace(",", "").replace("$", "").strip()
    try:
        number = float(cleaned)
        return number if number > 0 else None
    except ValueError:
        pass

    matches = re.findall(r"\d+(?:\.\d+)?", cleaned)
    if not matches:
        return None
    try:
        number = float(matches[0])
        return number if number > 0 else None
    except ValueError:
        return None


def extract_firmographic_size(
    firmo: dict[str, Any],
    search_row: dict[str, Any] | None = None,
) -> tuple[float | None, float | None]:
    """Revenue (USD) and employee count from firmographic, with optional search row fallback."""
    revenue_raw = firmo.get("revenue") or firmo.get("revenueAmount")
    employees_raw = firmo.get("employeeCount") or firmo.get("employees")

    revenue = parse_hg_numeric(revenue_raw)
    employees = parse_hg_numeric(employees_raw)

    if search_row:
        if revenue is None:
            revenue = parse_hg_numeric(
                search_row.get("revenueAmount") or search_row.get("revenue")
            )
        if employees is None:
            employees = parse_hg_numeric(
                search_row.get("employeeCount") or search_row.get("employees")
            )

    return revenue, employees
