from __future__ import annotations

import json
from pathlib import Path

from ..run_csv_repository import RunCsvRepository


def build_retry_input(failed_jsonl: Path, base_csv: Path, output_csv: Path, repo: RunCsvRepository) -> int:
    if not failed_jsonl.exists():
        raise FileNotFoundError(f"Failed JSONL not found: {failed_jsonl}")
    if failed_jsonl.is_dir():
        raise IsADirectoryError(f"Failed JSONL is a directory: {failed_jsonl}")
    if not base_csv.exists():
        raise FileNotFoundError(f"Base CSV not found: {base_csv}")
    if base_csv.is_dir():
        raise IsADirectoryError(f"Base CSV is a directory: {base_csv}")
    if output_csv.is_dir():
        raise IsADirectoryError(f"Output CSV is a directory: {output_csv}")

    wanted_ids: set[int] = set()
    with failed_jsonl.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                node = json.loads(line)
                if not isinstance(node, dict):
                    continue
            except Exception:
                continue
            word_id = node.get("word_id")
            if isinstance(word_id, float):
                raise ValueError(
                    f"Non-integer word_id in failed JSONL (float): {node}"
                )
            try:
                word_int = int(word_id)
            except Exception:
                continue
            if word_int <= 0:
                raise ValueError(
                    f"Non-positive word_id in failed JSONL: {word_int}"
                )
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
    for rec in table.records:
        try:
            word_id_val = rec.values[idx]
            if word_id_val is None:
                continue
            word_id_str = str(word_id_val).strip()
            if not word_id_str:
                continue
            if "." in word_id_str or "," in word_id_str:
                raise ValueError(
                    f"Non-integer word_id in base CSV (looks like float): {word_id_str}"
                )
            word_id = int(word_id_str)
        except ValueError as exc:
            raise exc
        if word_id in wanted_ids:
            rows.append(rec.values)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    repo.write_rows(output_csv, table.headers, rows)
    return len(rows)
