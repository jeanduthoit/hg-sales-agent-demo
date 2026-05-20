"""Allocate iteration-based output folders (no timestamps in names)."""

from __future__ import annotations

import re
from pathlib import Path

ORDINAL_WORDS = [
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
]


def _iteration_label(index: int) -> str:
    if 1 <= index <= len(ORDINAL_WORDS):
        return ORDINAL_WORDS[index - 1]
    return str(index)


def _iteration_title(label: str) -> str:
    if label.isdigit():
        return f"Iteration {label}"
    if label in ORDINAL_WORDS:
        return f"Iteration {label.title()}"
    return label.replace("_", " ").title()


def slugify_run_name(name: str) -> str:
    """User label → safe folder name, e.g. 'Test entretien mai' → test_entretien_mai."""
    text = name.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    if not text:
        return ""
    if text.startswith("iteration_"):
        return text
    return text


def _existing_indices(base: Path) -> list[int]:
    indices: list[int] = []
    if not base.is_dir():
        return indices
    for path in base.iterdir():
        if not path.is_dir():
            continue
        m = re.match(r"iteration_(\w+)$", path.name)
        if not m:
            continue
        word = m.group(1)
        if word in ORDINAL_WORDS:
            indices.append(ORDINAL_WORDS.index(word) + 1)
        elif word.isdigit():
            indices.append(int(word))
    return indices


def _unique_folder(root: Path, base_name: str) -> Path:
    candidate = root / base_name
    if not candidate.exists():
        return candidate
    n = 2
    while (root / f"{base_name}_{n}").exists():
        n += 1
    return root / f"{base_name}_{n}"


def prompt_run_name() -> str:
    """Ask in the terminal; empty answer = automatic iteration naming."""
    try:
        answer = input("\nOutput folder name (empty = automatic iteration): ").strip()
    except EOFError:
        answer = ""
    return answer


def allocate_iteration(
    base: Path | None = None,
    run_name: str | None = None,
    ask_name: bool = False,
) -> tuple[Path, str, str]:
    """
    Returns (folder_path, iteration_key, iteration_title).

    - No run_name, ask_name=False → iteration_one, iteration_two, …
    - run_name or ask_name → custom folder under outputs/ (e.g. demo_entretien_mai)
    """
    root = base or Path(__file__).resolve().parent / "outputs"
    root.mkdir(parents=True, exist_ok=True)

    label = slugify_run_name(run_name) if run_name else ""
    if ask_name and not label:
        label = slugify_run_name(prompt_run_name())

    if label:
        folder = _unique_folder(root, label)
        folder.mkdir(parents=True, exist_ok=True)
        key = folder.name
        title = _iteration_title(label)
        return folder, key, title

    indices = _existing_indices(root)
    next_idx = max(indices, default=0) + 1
    word = _iteration_label(next_idx)
    key = f"iteration_{word}"
    folder = root / key
    folder.mkdir(parents=True, exist_ok=True)
    return folder, key, _iteration_title(word)
