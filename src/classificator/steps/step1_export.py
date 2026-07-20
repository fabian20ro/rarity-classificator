from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter
from pathlib import Path

from ..constants import BASE_CSV_HEADERS
from ..run_csv_repository import RunCsvRepository
from ..word_store import WordStore


@dataclass(frozen=True)
class Step1Options:
    output_csv_path: Path
    dry_run: bool = False


def run_step1(options: Step1Options, *, word_store: WordStore, repo: RunCsvRepository) -> Path | None:
    words = sorted(word_store.fetch_all_words(), key=attrgetter("word_id"))
    rows = [[str(w.word_id), w.word, w.type] for w in words]
    if options.dry_run:
        print(f"Step 1 dry-run. Would export {len(words)} words to {options.output_csv_path}")
        return None
    repo.write_rows(options.output_csv_path, BASE_CSV_HEADERS, rows)
    print(f"Step 1 complete. Exported {len(words)} words to {options.output_csv_path}")
    return options.output_csv_path
