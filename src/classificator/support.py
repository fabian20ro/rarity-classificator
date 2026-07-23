from __future__ import annotations

import unicodedata
from pathlib import Path


def sanitize_run_slug(raw: str) -> str:
    if not isinstance(raw, str):
        raise TypeError(
            f"sanitize_run_slug expects str, got {type(raw).__name__}"
        )
    normalized = raw.strip().lower()
    normalized = unicodedata.normalize("NFC", normalized).casefold()
    valid = "".join(ch for ch in normalized if ch.isalnum() or ch == "_")
    if not valid:
        raise ValueError(
            f"Invalid run slug '{raw}'. Result is empty after sanitization."
        )
    if len(valid) > 40:
        raise ValueError(
            f"Invalid run slug '{raw}'. Length {len(valid)} exceeds maximum of 40 chars"
        )
    return valid


def median(values: list[int]) -> int:
    if not values:
        raise ValueError("median() requires non-empty values")
    sorted_vals = sorted(values)
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 1:
        return sorted_vals[mid]
    return round((sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0)


def load_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt file does not exist: {path}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Prompt file is empty: {path}")
    return content


def required_columns(actual: list[str], required: list[str], label: str) -> None:
    missing = [col for col in required if col not in actual]
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")
