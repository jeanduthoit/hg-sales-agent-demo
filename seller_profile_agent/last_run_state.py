"""Remember the last `npm run profile:seller` for chaining into `npm run pipeline`."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "output" / "seller_profiles"
STATE_FILE = PROFILE_DIR / ".last_profile_run.json"


def save_last_profile_run(
    *,
    company_input: str,
    company_slug: str,
    product_index: int,
    company_name: str,
    product_name: str,
) -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {
                "company_input": company_input,
                "company_slug": company_slug,
                "product_index": product_index,
                "company_name": company_name,
                "product_name": product_name,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def load_last_profile_run() -> dict | None:
    if not STATE_FILE.is_file():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if data.get("company_slug") and data.get("product_index"):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None
