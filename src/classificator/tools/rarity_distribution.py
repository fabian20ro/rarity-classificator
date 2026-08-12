from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..run_csv_repository import RunCsvRepository

_DEFAULT_LEVEL_COLUMNS = ("final_level", "rarity_level", "median_level")


@dataclass(frozen=True)
class RarityDistributionResult:
    csv_path: Path
    level_column: str
    total_rows: int
    distribution: dict[int, int]
    mode: int


def run_rarity_distribution(
    *,
    csv_path: Path,
    repo: RunCsvRepository,
    level_column: str | None = None,
) -> RarityDistributionResult:
    table = repo.read_table(csv_path)
    resolved_level_col = _resolve_level_column(table.headers, level_column)
    idx_level = table.headers.index(resolved_level_col)

    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    total_rows = 0

    for rec in table.records:
        vals = rec.values
        if len(vals) == 1 and vals[0] == "":
            continue
        total_rows += 1
        if idx_level >= len(vals):
            raise ValueError(f"Missing {resolved_level_col} at row {rec.line_number} in {csv_path}")
        raw_level = vals[idx_level].strip()
        level = _validate_level(raw_level, resolved_level_col, rec.line_number)
        distribution[level] += 1

    mode = max(distribution, key=distribution.get)
    print(
        f"input_csv={csv_path}",
        f"level_column={resolved_level_col}",
        f"mode={mode}",
        f"distribution=[1:{distribution[1]} 2:{distribution[2]} 3:{distribution[3]} ",
        f"4:{distribution[4]} 5:{distribution[5]}] total={total_rows}"
    )
    print(
        "distribution_pct=["
        + " ".join([f"{k}:{_pct(v, total_rows):.2f}%" for k, v in sorted(distribution.items())])
        + "]"
    )

    return RarityDistributionResult(
        csv_path=csv_path,
        level_column=resolved_level_col,
        total_rows=total_rows,
        distribution=distribution,
        mode=mode,
    )


def _resolve_level_column(headers: list[str], level_column: str | None) -> str:
    if level_column:
        if level_column not in headers:
            raise ValueError(f"CSV missing requested level column '{level_column}'")
        return level_column
    for col in _DEFAULT_LEVEL_COLUMNS:
        if col in headers:
            return col
    raise ValueError("CSV missing level column: final_level/rarity_level/median_level")


def _validate_level(raw_level: str, col_name: str, line_number: int) -> int:
    if isinstance(raw_level, str) and (not raw_level or not raw_level.strip()):
        raise ValueError(
            f"Invalid {col_name} '{raw_level}' at row {line_number}: not a number"
        ) from None
    try:
        level = int(raw_level)
    except ValueError as exc:
        raise ValueError(f"Invalid {col_name} '{raw_level}' at row {line_number}: not a number") from exc
    if level < 1 or level > 5:
        raise ValueError(f"Invalid {col_name} {level} at row {line_number}: must be between 1 and 5")
    return level


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return (part * 100.0) / total
