"""One item at a time; durable per-item records are the source for CSV projections."""

import hashlib
import json
import os
import time
import math
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path

from ..csv_codec import CsvCodec
from ..lock_manager import acquire_output_lock
from ..models import BaseWordRow
from ..scoring.base import BatchScorer, Outcome

PREDICTION_FIELDS = [
    "word_id",
    "word",
    "type",
    "status",
    "rarity_level",
    "p_L1",
    "p_L2",
    "p_L3",
    "p_L4",
    "p_L5",
    "expected_level",
    "confidence",
    "error",
    "tag",
    "scored_at",
    "latency_seconds",
]
RUN_FIELDS = [
    "word_id",
    "word",
    "type",
    "rarity_level",
    "tag",
    "confidence",
    "scored_at",
    "model",
    "run_slug",
]


def run_campaign(
    items: list[BaseWordRow],
    scorer: BatchScorer,
    output_dir: Path,
    *,
    config: dict,
    retry_failed: bool = False,
) -> Path:
    if not items or len({item.word_id for item in items}) != len(items):
        raise ValueError("Inventory must contain unique IDs and at least one word")
    if any(
        type(item.word_id) is not int or item.word_id <= 0 or not item.word.strip()
        for item in items
    ):
        raise ValueError("Inventory requires positive integer IDs and nonempty words")
    config = json.loads(json.dumps(config, sort_keys=True, allow_nan=False))
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": 1,
        "config": config,
        "implementation_sha256": _implementation_hash(),
        "inventory_sha256": hashlib.sha256(
            json.dumps(
                [asdict(item) for item in items], ensure_ascii=False, sort_keys=True
            ).encode()
        ).hexdigest(),
    }
    with acquire_output_lock(output_dir / "campaign"):
        manifest_path = output_dir / "manifest.json"
        if manifest_path.exists():
            if json.loads(manifest_path.read_text()) != manifest:
                raise ValueError(
                    "Campaign configuration or vocabulary changed; use a new directory"
                )
        else:
            if any(
                path.name not in {"campaign.lock", "manifest.tmp"} for path in output_dir.iterdir()
            ):
                raise ValueError("Existing campaign artifacts have no manifest")
            _write_json(manifest_path, manifest)
        records_dir = output_dir / "records"
        records_dir.mkdir(exist_ok=True)
        records = {}
        for item in items:
            path = records_dir / f"{item.word_id}.json"
            if path.exists():
                record = json.loads(path.read_text())
                if (record.get("word_id"), record.get("word"), record.get("type")) != (
                    item.word_id,
                    item.word,
                    item.type,
                ):
                    raise ValueError("Corrupt campaign checkpoint identity")
                try:
                    Outcome(**{field.name: record[field.name] for field in fields(Outcome)})
                except (ValueError, KeyError, TypeError) as exc:
                    raise ValueError("Corrupt campaign checkpoint outcome") from exc
                records[item.word_id] = _summary(record)
        try:
            for item in items:
                record = records.get(item.word_id)
                if record is not None and not (retry_failed and record["status"] == "failed"):
                    continue
                started = time.perf_counter()
                outcomes = scorer.score_batch([item])
                elapsed = time.perf_counter() - started
                if len(outcomes) != 1 or outcomes[0].word_id != item.word_id:
                    raise ValueError("Scorer must return exactly one outcome for the requested ID")
                outcome = outcomes[0]
                record = {
                    **asdict(outcome),
                    "word": item.word,
                    "type": item.type,
                    "scored_at": datetime.now(timezone.utc).isoformat(),
                    "expected_level": outcome.expected_level,
                    "latency_seconds": elapsed,
                }
                _write_json(records_dir / f"{item.word_id}.json", record)
                records[item.word_id] = _summary(record)
                if len(records) % 100 == 0:
                    _export(list(records.values()), output_dir, config, len(items))
        finally:
            _export(list(records.values()), output_dir, config, len(items))
    return output_dir / "predictions.csv"


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _export(records: list[dict], output_dir: Path, config: dict, total: int) -> None:
    predictions, runs = [], []
    for record in sorted(records, key=lambda row: row["word_id"]):
        row = dict(record)
        row.update({f"p_L{i}": p for i, p in enumerate(record["probabilities"], 1)})
        predictions.append([_cell(row.get(key)) for key in PREDICTION_FIELDS])
        if record["status"] == "scored" and record["confidence"] is not None:
            row.update(
                model=config.get("model", "unknown"),
                run_slug=config.get("run_slug", output_dir.name),
            )
            runs.append([_cell(row.get(key)) for key in RUN_FIELDS])
    codec = CsvCodec()
    codec.write_table_atomic(output_dir / "predictions.csv", PREDICTION_FIELDS, predictions)
    codec.write_table_atomic(output_dir / "run.csv", RUN_FIELDS, runs)
    for filename, status in [("failures.csv", "failed"), ("review.csv", "unresolved")]:
        codec.write_table_atomic(
            output_dir / filename,
            PREDICTION_FIELDS,
            [row for row in predictions if row[3] == status],
        )

    durations = sorted(record["latency_seconds"] for record in records)
    counts = {
        status: sum(record["status"] == status for record in records)
        for status in ("scored", "failed", "unresolved")
    }
    _write_json(
        output_dir / "summary.json",
        {
            "total": total,
            **counts,
            "pending": total - len(records),
            "total_seconds": sum(durations),
            "latency_p50": durations[math.ceil(len(durations) * 0.5) - 1] if durations else None,
            "latency_p95": durations[math.ceil(len(durations) * 0.95) - 1] if durations else None,
            "timing_scope": "scorer wall time including per-item preflight; latest attempt per ID",
        },
    )


def _cell(value) -> str:
    return "" if value is None else str(value)


def _summary(record: dict) -> dict:
    # Keep large HTTP payloads on disk, not in the campaign's growing working set.
    return {key: value for key, value in record.items() if key not in {"request", "response"}}


def _implementation_hash() -> str:
    root = Path(__file__).resolve().parent.parent
    sources = sorted((root / "scoring").glob("*.py")) + [
        Path(__file__).resolve(),
        root / "evaluation" / "cli.py",
    ]
    digest = hashlib.sha256()
    for source in sources:
        digest.update(str(source.relative_to(root)).encode())
        digest.update(source.read_bytes())
    return digest.hexdigest()
