"""Offline, optional wordfreq export restricted to an explicit word inventory."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import unicodedata
from pathlib import Path
from tempfile import TemporaryDirectory

from ..run_csv_repository import RunCsvRepository


def _normalize(word: str) -> str:
    return unicodedata.normalize("NFC", word).translate(str.maketrans("şţŞŢ", "șțȘȚ")).casefold()


def export_wordfreq(vocabulary_csv: Path, output_csv: Path) -> dict:
    """Export observed Romanian frequencies; missing/censored words remain absent."""
    metadata_path = output_csv.with_suffix(output_csv.suffix + ".metadata.json")
    for path in (output_csv, metadata_path):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Export artifact already exists: {path}")
    try:
        import wordfreq

        package_version = importlib.metadata.version("wordfreq")
    except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
        raise RuntimeError("Optional dependency missing: pip install wordfreq") from exc

    repo = RunCsvRepository()
    vocabulary = repo.load_base_rows(vocabulary_csv)
    ids = [row.word_id for row in vocabulary]
    if not ids or min(ids) <= 0 or len(ids) != len(set(ids)):
        raise ValueError("Vocabulary must have positive unique IDs and at least one entry")
    frequencies = {}
    for word, value in wordfreq.get_frequency_dict("ro", wordlist="best").items():
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Invalid corpus frequency for {word!r}")
        key = _normalize(word)
        if key in frequencies and frequencies[key] != value:
            raise ValueError(f"Conflicting corpus frequencies after normalization: {word!r}")
        frequencies[key] = value
    exported = []
    seen = set()
    for row in vocabulary:
        key = _normalize(row.word)
        if key not in seen and frequencies.get(key, 0) > 0:
            exported.append([row.word, str(frequencies[key])])
        seen.add(key)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".wordfreq-", dir=output_csv.parent) as temporary:
        staged_csv = Path(temporary) / output_csv.name
        staged_metadata = Path(temporary) / metadata_path.name
        repo.write_rows(staged_csv, ["word", "frequency"], exported)
        metadata = {
            "schema_version": 1,
            "package": "wordfreq",
            "package_version": package_version,
            "language": "ro",
            "wordlist": "best",
            "inventory_count": len(vocabulary),
            "exported_count": len(exported),
            "vocabulary_sha256": hashlib.sha256(vocabulary_csv.read_bytes()).hexdigest(),
            "frequencies_sha256": hashlib.sha256(staged_csv.read_bytes()).hexdigest(),
            "coverage_note": "Romanian has a small word list; missing/zero entries are censored, not evidence of true zero use or rarity level 5.",
        }
        staged_metadata.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        published = []
        try:
            # Publish the CSV last; hard links refuse to overwrite concurrent writers.
            for source, target in ((staged_metadata, metadata_path), (staged_csv, output_csv)):
                os.link(source, target)
                published.append(target)
        except BaseException:
            for path in published:
                path.unlink()
            raise
    return {**metadata, "output_csv": output_csv, "metadata_path": metadata_path}
