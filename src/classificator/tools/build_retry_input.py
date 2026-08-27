from __future__ import annotations

import json
import logging
from pathlib import Path

from ..run_csv_repository import RunCsvRepository


log = logging.getLogger(__name__)


def _validate_jsonl_word_id(value, record):
    """Validate a word_id from JSONL; raise on corruption, return int or None to skip."""
    if isinstance(value, bool):
        raise ValueError(f"Boolean word_id in failed JSONL: {record}")
    if isinstance(value, float):
        raise ValueError(f"Non-integer word_id in failed JSONL (float): {record}")
    if isinstance(value, (list, dict)):
        raise ValueError(
            f"Unsupported word_id type in failed JSONL ({type(value).__name__}): {value!r}"
        )
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None  # missing data — skip silently per contract
    if isinstance(value, str):
        raise ValueError(f"String word_id in failed JSONL: {value!r}")

    try:
        word_int = int(value)
    except ValueError:
        raise ValueError(
            f"Unparseable word_id in failed JSONL: {value!r}"
        ) from None
    if word_int <= 0:
        raise ValueError(f"Non-positive word_id in failed JSONL: {word_int}")
    return word_int


def build_retry_input(
    failed_jsonl: Path, base_csv: Path, output_csv: Path, repo: RunCsvRepository
) -> int:
    if not failed_jsonl.exists():
        raise FileNotFoundError(f"Failed JSONL not found: {failed_jsonl}")
    if failed_jsonl.is_dir():
        raise IsADirectoryError(f"Failed JSONL path is a directory: {failed_jsonl}")
    if not base_csv.exists():
        raise FileNotFoundError(f"Base CSV not found: {base_csv}")
    if base_csv.is_dir():
        raise IsADirectoryError(f"Base CSV is a directory: {base_csv}")
    if output_csv.is_dir():
        raise IsADirectoryError(f"Output CSV path is a directory: {output_csv}")
    if output_csv.exists() and not output_csv.is_dir():
        raise FileExistsError(
            f"Output CSV already exists (refusing to overwrite): {output_csv}"
        )

    wanted_ids: set[int] = set()
    with failed_jsonl.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue

            # Validate JSON parse independently — exceptions here (malformed
            # lines) surface immediately so a broken producer is visible rather
            # than masked by silent skip. The next check (`isinstance(node, dict)`
            # and the rest of this loop's logic) runs OUTSIDE this try/except so
            # failures there propagate with their own context.
            try:
                node = json.loads(line)
            except Exception as parse_exc:
                raise ValueError(
                    f"Unparseable failed-JSONL line: {line!r}"
                ) from parse_exc

            if not isinstance(node, dict):
                # Valid JSON but wrong shape — signals schema drift in the
                # producer of the failed JSONL (e.g. it started emitting arrays
                # or bare strings after a code change). Surface immediately so
                # the pipeline break is visible rather than masked by silent skip.
                raise ValueError(
                    f"Non-dict record in failed JSONL ({type(node).__name__}): {node!r}"
                )

            word_id = node.get("word_id")
            # All word_id validation lives in `_validate_jsonl_word_id` so the
            # documented boundary has a single source of truth: None/empty-string
            # is skipped silently (missing data); every other malformed or
            # non-positive value raises with a unique, actionable message.
            word_int = _validate_jsonl_word_id(word_id, node)
            if word_int is None:
                continue
            wanted_ids.add(word_int)

    table = repo.read_table(base_csv)
    if "word_id" not in table.headers:
        raise ValueError(f"Base CSV must contain word_id: {base_csv}")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    if not table.records:
        repo.write_rows(output_csv, table.headers, [])
        return 0

    idx = table.headers.index("word_id")
    rows = []
    for line_num, rec in enumerate(table.records, start=1):
        word_id_val = rec.values[idx]
        if word_id_val is None:
            continue
        word_id_str = str(word_id_val).strip()
        if not word_id_str:
            continue
        if "." in word_id_str or "," in word_id_str:
            raise ValueError(
                f"Non-integer word_id at base CSV record {line_num} (looks like float): {word_id_str}"
            )
        try:
            word_id = int(word_id_str)
        except ValueError as inner_exc:
            raise ValueError(
                f"Invalid word_id at base CSV record {line_num}: '{word_id_str}'"
            ) from None
        if word_id in wanted_ids:
            rows.append(rec.values)

    seen_ids: set[int] = set()
    deduped_rows = []
    for row_idx, row in enumerate(rows):
        wid_val = row[idx] if idx < len(row) else None
        # Every row entering this pass was matched against `wanted_ids`, which
        # already validated the word_id as a positive integer. An unparseable
        # value here means the base CSV contained inconsistent data (e.g. a
        # non-string ID that parsed in JSONL but not in CSV) — fail fast so
        # corruption is visible rather than masked by silent dedup dropping.
        if wid_val is None or wid_val == "":
            continue
        try:
            wid = int(str(wid_val).strip())
        except ValueError:
            raise ValueError(
                f"Unparseable word_id in matched row at index {row_idx}: '{wid_val}'"
            )
        if wid is not None and wid not in seen_ids:
            seen_ids.add(wid)
            deduped_rows.append(row)

    if seen_ids != wanted_ids:
        missing = sorted(wanted_ids - seen_ids)
        log.warning(
            "Retry input: %d requested word_id(s) not found in base CSV %s: %s",
            len(missing),
            base_csv,
            missing,
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    repo.write_rows(output_csv, table.headers, deduped_rows)
    return len(deduped_rows)