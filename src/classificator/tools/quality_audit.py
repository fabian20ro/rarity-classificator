from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..run_csv_repository import RunCsvRepository


@dataclass(frozen=True)
class QualityAuditResult:
    distribution: dict[int, int]
    total_rows: int
    level_column: str
    l1_jaccard: float | None
    l1_intersection: int | None
    l1_candidate_size: int
    l1_reference_size: int | None
    anchor_precision: float | None
    anchor_recall: float | None
    passed: bool
    failures: list[str]


def run_quality_audit(
    *,
    candidate_csv: Path,
    reference_csv: Path | None = None,
    anchor_l1_file: Path | None = None,
    min_l1_jaccard: float | None = None,
    min_anchor_l1_precision: float | None = None,
    min_anchor_l1_recall: float | None = None,
    repo: RunCsvRepository,
) -> QualityAuditResult:
    candidate = _load_run(candidate_csv, repo)
    failures: list[str] = []

    l1_jaccard = None
    l1_intersection = None
    l1_reference_size = None

    dist = candidate["distribution"]

    if reference_csv is not None:
        reference = _load_run(reference_csv, repo)
        inter = len(candidate["l1_word_ids"].intersection(reference["l1_word_ids"]))
        union = len(candidate["l1_word_ids"]) + len(reference["l1_word_ids"]) - inter
        jaccard = _ratio(inter, union)
        l1_jaccard = jaccard
        l1_intersection = inter
        l1_reference_size = len(reference["l1_word_ids"])
        if min_l1_jaccard is not None and jaccard < min_l1_jaccard:
            failures.append(f"l1_jaccard {jaccard:.4f} < min {min_l1_jaccard:.4f}")

    anchor_precision = None
    anchor_recall = None
    if anchor_l1_file is not None:
        anchors = _load_anchor_words(anchor_l1_file)
        inter = len(candidate["l1_words"].intersection(anchors))
        precision = _ratio(inter, len(candidate["l1_words"]))
        recall = _ratio(inter, len(anchors))
        anchor_precision = precision
        anchor_recall = recall
        if min_anchor_l1_precision is not None and precision < min_anchor_l1_precision:
            failures.append(f"anchor_l1_precision {precision:.4f} < min {min_anchor_l1_precision:.4f}")
        if min_anchor_l1_recall is not None and recall < min_anchor_l1_recall:
            failures.append(f"anchor_l1_recall {recall:.4f} < min {min_anchor_l1_recall:.4f}")

    passed = not failures
    return QualityAuditResult(
        distribution=dist,
        total_rows=candidate["total_rows"],
        level_column=candidate["level_column"],
        l1_jaccard=l1_jaccard,
        l1_intersection=l1_intersection,
        l1_candidate_size=len(candidate["l1_word_ids"]),
        l1_reference_size=l1_reference_size,
        anchor_precision=anchor_precision,
        anchor_recall=anchor_recall,
        passed=passed,
        failures=failures,
    )


def _load_run(path: Path, repo: RunCsvRepository) -> dict[str, object]:
    table = repo.read_table(path)
    if "word_id" not in table.headers or "word" not in table.headers:
        raise ValueError(f"CSV must contain word_id and word: {path}")
    _level_candidates = ("final_level", "rarity_level", "median_level")
    present = [c for c in _level_candidates if c in table.headers]
    if len(present) > 1:
        raise ValueError(
            f"CSV has ambiguous level columns ({', '.join(present)}): {path}"
        )
    if not present:
        raise ValueError("CSV missing level column: final_level/rarity_level/median_level")
    level_col = present[0]

    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    l1_word_ids: set[int] = set()
    l1_words: set[str] = set()
    total_rows = 0

    headers = table.headers
    idx_word_id = headers.index("word_id")
    idx_word = headers.index("word")
    idx_level = headers.index(level_col)

    for rec in table.records:
        vals = rec.values
        if not any(v.strip() for v in vals):
            continue
        total_rows += 1
        try:
            word_id = int(vals[idx_word_id])
        except ValueError:
            raise ValueError(
                f"Non-numeric word_id at row {rec.line_number} in {path}"
            ) from None
        level = int(vals[idx_level])
        if level < 1 or level > 5:
            raise ValueError(f"Invalid level at row {rec.line_number} in {path}")
        word = vals[idx_word].strip()
        distribution[level] += 1
        if level == 1 and word:
            l1_word_ids.add(word_id)
            l1_words.add(word.lower())

    return {
        "level_column": level_col,
        "total_rows": total_rows,
        "distribution": distribution,
        "l1_word_ids": l1_word_ids,
        "l1_words": l1_words,
    }


def _load_anchor_words(path: Path) -> set[str]:
    words: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        t = raw.strip()
        if not t or t.startswith("#"):
            continue
        words.add(t.lower())
    if not words:
        raise ValueError(f"Anchor file has no usable words: {path}")
    return words


def _ratio(n: int, d: int) -> float:
    if d <= 0:
        return 0.0
    return n / d
