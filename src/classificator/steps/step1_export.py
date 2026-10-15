from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import csv
import sys

from ..constants import BASE_CSV_HEADERS
from ..run_csv_repository import RunCsvRepository
from ..word_store import WordStore


@dataclass(frozen=True)
class Step1Options:
    output_csv_path: Path
    dry_run: bool = False


def run_step1(options: Step1Options, *, word_store: WordStore, repo: RunCsvRepository) -> Path | None:
    words = list(word_store.fetch_all_words())
    for row in words:
        if row.word_id is None:
            raise ValueError(
                f"step1 export: null word_id (word={row.word!r}, type={row.type!r}); "
                "refusing to export 'None' as word_id"
            )
    rows = [[str(row.word_id), row.word, row.type] for row in sorted(words, key=lambda row: row.word_id)]
    word_count = len(rows)
    if options.dry_run:
        print(f"Step 1 dry-run. Would export {word_count} words to {options.output_csv_path}")
        if word_count:
            type_counts = Counter(row.type for row in words)
            print("Types: " + ", ".join(f"{t}={n}" for t, n in sorted(type_counts.items(), key=lambda x: (-x[1], x[0]))))
            writer = csv.writer(sys.stdout, lineterminator="\n")
            writer.writerow(BASE_CSV_HEADERS)
            writer.writerows(rows[:3])
        return None
    repo.write_rows(options.output_csv_path, BASE_CSV_HEADERS, rows)
    print(f"Step 1 complete. Exported {word_count} words to {options.output_csv_path}")
    return options.output_csv_path
