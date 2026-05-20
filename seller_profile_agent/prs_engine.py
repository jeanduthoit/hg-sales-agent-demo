"""Deterministic PRS scoring engine (la-methodologie.md)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from prs_criteria import display_name
from scoring_display import fmt_num, reliability_step

WEIGHTS: dict[str, float] = {
    "taille": 0.25,
    "budget": 0.20,
    "besoin": 0.20,
    "achat": 0.20,
    "dynamique": 0.15,
}


@dataclass
class CriterionResult:
    criterion_id: str
    score: float | None
    reliability: float
    weight: float
    contribution: float
    included_in_prs: bool
    calculation_steps: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProspectScore:
    rank: int = 0
    company_name: str = ""
    domain: str = ""
    prs: float = 0.0
    reliability_global: float = 0.0
    criteria: dict[str, CriterionResult] = field(default_factory=dict)
    raw_notes: list[str] = field(default_factory=list)


def _log10_safe(value: float) -> float | None:
    if value is None or value <= 0:
        return None
    return math.log10(value)


def _clamp_score(value: float) -> float:
    """PRS criterion scores are always on [0, 100]."""
    return max(0.0, min(100.0, value))


def score_taille(revenue: Any, employees: Any) -> CriterionResult:
    steps: list[str] = []
    inputs: dict[str, Any] = {"revenue": revenue, "employees": employees}

    s_rev: float | None = None
    s_emp: float | None = None

    try:
        rev = float(revenue) if revenue is not None else None
    except (TypeError, ValueError):
        rev = None
    try:
        emp = float(employees) if employees is not None else None
    except (TypeError, ValueError):
        emp = None

    if rev and rev > 0:
        log_num = _log10_safe(rev / 1_000_000)
        if log_num is not None:
            raw_rev = 100.0 * log_num / math.log10(1000)
            s_rev = _clamp_score(raw_rev)
            steps.append(
                "S_rev = max(0, min(100, 100 × log10(revenue / 1,000,000) / log10(1000)))"
            )
            steps.append(
                f"      = max(0, min(100, 100 × log10({rev:,.0f} / 1,000,000) / "
                f"{fmt_num(math.log10(1000))}))"
            )
            if raw_rev < 0:
                steps.append(f"      = {fmt_num(raw_rev)} → floored to 0 (revenue below $1M anchor)")
            steps.append(f"      = {fmt_num(s_rev)}")

    if emp and emp > 0:
        s_emp = min(100.0, 100.0 * emp / 10_000.0)
        steps.append("S_emp = min(100, 100 × employeeCount / 10,000)")
        steps.append(f"      = min(100, 100 × {emp:,.0f} / 10,000)")
        steps.append(f"      = {fmt_num(s_emp)}")

    if s_rev is not None and s_emp is not None:
        s_size = max(s_rev, s_emp)
        steps.append(f"S_size = max(S_rev, S_emp) = max({fmt_num(s_rev)}, {fmt_num(s_emp)}) = {fmt_num(s_size)}")
    elif s_rev is not None:
        s_size = s_rev
        steps.append(f"S_size = S_rev = {fmt_num(s_size)} (employeeCount missing)")
    elif s_emp is not None:
        s_size = s_emp
        steps.append(f"S_size = S_emp = {fmt_num(s_size)} (revenue missing)")
    else:
        s_size = None
        steps.append("S_size = not calculable (revenue and employeeCount missing)")

    present = int(rev is not None and rev > 0) + int(emp is not None and emp > 0)
    r_size = present / 2.0
    steps.append(reliability_step("size", present, 2, r_size))

    score = s_size if s_size is not None else None
    contribution = (WEIGHTS["taille"] * score) if score is not None else 0.0

    return CriterionResult(
        criterion_id="taille",
        score=score,
        reliability=r_size,
        weight=WEIGHTS["taille"],
        contribution=contribution,
        included_in_prs=score is not None,
        calculation_steps=steps,
        inputs=inputs,
    )


def score_budget(it_budget: Any, unknown_row_count: Any = None) -> CriterionResult:
    steps: list[str] = []
    inputs: dict[str, Any] = {
        "it_budget": it_budget,
        "unknown_row_count": unknown_row_count,
    }

    try:
        budget = float(it_budget) if it_budget is not None else None
    except (TypeError, ValueError):
        budget = None

    s_budget: float | None = None
    if budget and budget > 0:
        log_num = _log10_safe(budget / 100_000.0)
        if log_num is not None:
            raw_budget = 100.0 * log_num / 4.0
            s_budget = _clamp_score(raw_budget)
            steps.append(
                "S_budget = max(0, min(100, 100 × log10(totalSpendAmount / 100,000) / 4))"
            )
            steps.append(f"       = max(0, min(100, 100 × log10({budget:,.0f} / 100,000) / 4))")
            if raw_budget < 0:
                steps.append(
                    f"       = {fmt_num(raw_budget)} → floored to 0 (Total IT spend below $100k anchor)"
                )
            steps.append(f"       = {fmt_num(s_budget)}")
    else:
        steps.append("S_budget = not calculable (Total IT spend missing or zero)")

    present_budget = int(budget is not None and budget > 0)
    present_unknown = int(unknown_row_count is not None)
    r_budget = (present_budget + present_unknown) / 2.0
    steps.append(reliability_step("budget", present_budget + present_unknown, 2, r_budget))

    score = s_budget
    contribution = (WEIGHTS["budget"] * score) if score is not None else 0.0

    return CriterionResult(
        criterion_id="budget",
        score=score,
        reliability=r_budget,
        weight=WEIGHTS["budget"],
        contribution=contribution,
        included_in_prs=score is not None,
        calculation_steps=steps,
        inputs=inputs,
    )


def score_besoin(intensity_max: Any, category_name: str | None) -> CriterionResult:
    steps: list[str] = []
    inputs = {"intensity_max": intensity_max, "category_name": category_name}

    category_ok = bool(category_name)
    intensity_val: float | None = None
    try:
        if intensity_max is not None:
            intensity_val = float(intensity_max)
    except (TypeError, ValueError):
        intensity_val = None

    if intensity_val is not None:
        s_need = min(100.0, intensity_val)
        steps.append(f"HG category: {category_name}")
        steps.append(f"max(products.intensity) = {fmt_num(intensity_val)}")
        steps.append(
            f"S_need = min(100, intensity_max) = min(100, {fmt_num(intensity_val)}) = {fmt_num(s_need)}"
        )
    else:
        s_need = 0.0 if category_ok else None
        if category_ok:
            steps.append(f"HG category: {category_name}")
            steps.append("No intensity in target category → S_need = 0")
        else:
            steps.append("S_need = not calculable (category not resolved)")

    present_cat = int(category_ok)
    present_int = int(intensity_val is not None)
    r_need = (present_cat + present_int) / 2.0
    steps.append(reliability_step("need", present_cat + present_int, 2, r_need))

    score = s_need if s_need is not None else None
    contribution = (WEIGHTS["besoin"] * score) if score is not None else 0.0

    return CriterionResult(
        criterion_id="besoin",
        score=score,
        reliability=r_need,
        weight=WEIGHTS["besoin"],
        contribution=contribution,
        included_in_prs=score is not None,
        calculation_steps=steps,
        inputs=inputs,
    )


def _freshness_multiplier(days: int) -> tuple[float, str]:
    if days <= 30:
        return 1.0, f"days_since_last_seen = {days} (≤ 30) → freshness_multiplier = 1.0"
    if days <= 90:
        return 0.7, f"days_since_last_seen = {days} (31–90) → freshness_multiplier = 0.7"
    return 0.3, f"days_since_last_seen = {days} (> 90) → freshness_multiplier = 0.3"


def score_achat(
    topic_score: Any,
    last_seen_at: str | None,
    end_date: str | None = None,
) -> CriterionResult:
    steps: list[str] = []
    inputs = {"topic_score": topic_score, "last_seen_at": last_seen_at}

    try:
        raw_score = float(topic_score) if topic_score is not None else None
    except (TypeError, ValueError):
        raw_score = None

    if raw_score is None:
        steps.append("No company_intent topic for target product → S_intent = 0")
        s_intent = 0.0
        r_intent = 0.0
        steps.append("reliability_intent = 0 (topics[].score or topics[].last_seen_at missing)")
    else:
        days = 999
        if last_seen_at:
            try:
                seen = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
                end = (
                    datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    if end_date
                    else datetime.now(timezone.utc)
                )
                days = max(0, (end - seen).days)
            except ValueError:
                days = 999
        freshness, fresh_line = _freshness_multiplier(days)
        s_intent = min(100.0, raw_score * freshness)
        steps.append(f"topics[].score = {fmt_num(raw_score)}")
        steps.append(fresh_line)
        steps.append(
            f"S_intent = min(100, topics[].score × freshness_multiplier) "
            f"= min(100, {fmt_num(raw_score)} × {freshness}) = {fmt_num(s_intent)}"
        )
        present = sum(
            [
                int(raw_score is not None),
                int(last_seen_at is not None),
                int(last_seen_at is not None),
            ]
        )
        r_intent = present / 3.0
        steps.append(reliability_step("intent", present, 3, r_intent))

    contribution = WEIGHTS["achat"] * (s_intent if s_intent is not None else 0.0)

    return CriterionResult(
        criterion_id="achat",
        score=s_intent,
        reliability=r_intent if raw_score is not None else 0.0,
        weight=WEIGHTS["achat"],
        contribution=contribution,
        included_in_prs=True,
        calculation_steps=steps,
        inputs=inputs,
    )


def score_dynamique(momentum: Any, series_found: bool) -> CriterionResult:
    steps: list[str] = []
    inputs = {"intensity_momentum": momentum, "series_found": series_found}

    if not series_found:
        s_momentum = 50.0
        steps.append("Product absent from install time series → S_momentum = 50 (neutral)")
        r_momentum = 0.5
    else:
        try:
            m = float(momentum)
        except (TypeError, ValueError):
            m = 0.0
        if m > 0:
            s_momentum = 100.0
            steps.append(f"intensity_momentum = {fmt_num(m)} (> 0) → S_momentum = 100")
        elif m < 0:
            s_momentum = 0.0
            steps.append(f"intensity_momentum = {fmt_num(m)} (< 0) → S_momentum = 0")
        else:
            s_momentum = 50.0
            steps.append("intensity_momentum = 0 → S_momentum = 50")
        r_momentum = 1.0

    steps.append(f"reliability_momentum = {fmt_num(r_momentum)}")

    return CriterionResult(
        criterion_id="dynamique",
        score=s_momentum,
        reliability=r_momentum,
        weight=WEIGHTS["dynamique"],
        contribution=WEIGHTS["dynamique"] * s_momentum,
        included_in_prs=True,
        calculation_steps=steps,
        inputs=inputs,
    )


def aggregate_prs(criteria: dict[str, CriterionResult]) -> tuple[float, float, list[str]]:
    steps: list[str] = []
    prs_sum = 0.0
    weight_sum = 0.0
    rel_sum = 0.0
    rel_weight_sum = 0.0

    for cid, result in criteria.items():
        if cid.startswith("_"):
            continue
        w = WEIGHTS[cid]
        if result.included_in_prs and result.score is not None:
            prs_sum += w * result.score
            weight_sum += w
            steps.append(
                f"  + {fmt_num(w)} × {fmt_num(result.score)} ({display_name(cid)}) "
                f"= {fmt_num(w * result.score)}"
            )
        rel_sum += w * result.reliability
        rel_weight_sum += w

    if weight_sum > 0:
        prs = prs_sum / weight_sum
        steps.insert(
            0,
            f"Prospect Revenue Score = sum(w_i × S_i) / sum(w_i) = {fmt_num(prs_sum)} / "
            f"{fmt_num(weight_sum)} = {fmt_num(prs)}",
        )
    else:
        prs = 0.0
        steps.insert(0, "Prospect Revenue Score = 0 (no criteria calculable)")

    r_global = rel_sum / rel_weight_sum if rel_weight_sum else 0.0
    steps.append(
        f"PRS score reliability = {fmt_num(rel_sum)} / {fmt_num(rel_weight_sum)} = {fmt_num(r_global)}"
    )

    return prs, r_global, steps
