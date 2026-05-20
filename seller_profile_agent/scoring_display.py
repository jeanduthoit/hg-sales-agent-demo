"""Display helpers for scoring steps (English labels, integer scores)."""

from __future__ import annotations


def fmt_num(value: float | None) -> str:
    if value is None:
        return "N/A"
    v = float(value)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def reliability_step(name: str, present: int, total: int, value: float) -> str:
    return f"reliability_{name} = ({present} / {total}) = {fmt_num(value)}"
