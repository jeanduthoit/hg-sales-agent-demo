"""Legacy entry point — delegates to executive iteration reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from executive_reports import write_iteration_reports
from iteration_manager import allocate_iteration
from prs_engine import ProspectScore


def write_reports(
    output_dir: Path,
    seller_meta: dict[str, Any],
    results: list[ProspectScore],
    seller_profile: dict[str, Any] | None = None,
    profile_source: Path | None = None,
) -> tuple[Path, Path]:
    """
    Write executive iteration folder. Returns (executive_summary, technical_scoring) paths.
    """
    iteration_dir, _key, iteration_title = allocate_iteration(
        output_dir.parent / "outputs" if output_dir.name == "prospect_scores" else output_dir
    )
    seller = seller_profile or {}
    prof_path = profile_source or Path("seller_profile.json")
    paths = write_iteration_reports(
        iteration_dir,
        iteration_title,
        seller_meta,
        seller,
        results,
        prof_path,
    )
    return paths["executive_summary.md"], paths["technical_scoring.md"]
