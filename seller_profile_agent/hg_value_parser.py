"""Parse numeric values from HG firmographic and search fields."""

from __future__ import annotations

import re
from typing import Any, Literal

ParseStrategy = Literal["lower", "upper"]

_RANGE_RE = re.compile(
    r"from\s+[\$]?\s*([\d,]+(?:\.\d+)?)\s+to\s+[\$]?\s*([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)


def is_hg_bucket_range(value: Any) -> bool:
    """True when HG encodes a size band (e.g. 'From $10M to $49,999,999'), not a point estimate."""
    if value is None:
        return False
    text = str(value).strip().lower()
    return "from" in text and " to " in text


def _parse_number_token(token: str) -> float | None:
    cleaned = token.replace(",", "").replace("$", "").strip()
    if not cleaned:
        return None
    try:
        number = float(cleaned)
        return number if number > 0 else None
    except ValueError:
        return None


def _bounds_from_range(text: str) -> tuple[float, float] | None:
    match = _RANGE_RE.search(text)
    if not match:
        return None
    low = _parse_number_token(match.group(1))
    high = _parse_number_token(match.group(2))
    if low is None or high is None:
        return None
    if high < low:
        low, high = high, low
    return low, high


def parse_hg_numeric(
    value: Any,
    *,
    strategy: ParseStrategy = "lower",
) -> float | None:
    """
    Convert HG revenue, employee, or spend fields to a positive number.
    Handles plain numbers and range strings such as 'From $10,000,000 to $49,999,999'.
    For ranges: lower = min bound, upper = max bound.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number > 0 else None

    text = str(value).strip()
    if not text:
        return None

    bounds = _bounds_from_range(text)
    if bounds:
        low, high = bounds
        if strategy == "upper":
            return high
        return low

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
    *,
    strategy: ParseStrategy = "lower",
) -> tuple[float | None, float | None]:
    """
    Revenue (USD) and employee count from firmographic.
    Uses raw HG firmographic values only (range lower bound for HG banded strings).
    Never falls back to search row values (those are search-bucket proxies).
    """
    _ = search_row  # kept for call-site compatibility; intentionally unused
    revenue_raw = firmo.get("revenue") or firmo.get("revenueAmount")
    employees_raw = firmo.get("employeeCount") or firmo.get("employees")

    revenue = parse_hg_numeric(revenue_raw, strategy=strategy)
    employees = parse_hg_numeric(employees_raw, strategy=strategy)
    return revenue, employees
