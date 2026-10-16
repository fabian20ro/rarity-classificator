"""Prepare a frozen, offline evaluation dataset from an explicit vocabulary."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory


def _lexeme(word: str) -> str:
    return unicodedata.normalize("NFC", word).translate(str.maketrans("şţŞŢ", "șțȘȚ")).casefold()


def _game_key(word: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", _lexeme(word))
        if not unicodedata.combining(char)
    ).upper()


def _read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if not required <= set(headers) or len(headers) != len(set(headers)):
            raise ValueError(
                f"{path}: required columns {sorted(required)}; duplicate columns forbidden"
            )
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"{path}: malformed CSV row")
    return rows


def _vocabulary(path: Path) -> list[dict[str, str]]:
    rows = _read_csv(path, {"word_id", "word", "type"})
    if not rows:
        raise ValueError("Vocabulary must contain at least one entry")
    ids: set[int] = set()
    for row in rows:
        try:
            word_id = int(row["word_id"])
        except ValueError as exc:
            raise ValueError("word_id must be a positive integer") from exc
        if word_id <= 0 or word_id in ids:
            raise ValueError("word_id must be positive and unique")
        if not row["word"].strip() or not row["type"].strip():
            raise ValueError("word and type must be nonempty")
        ids.add(word_id)
        row["word_id"] = str(word_id)
    return sorted(rows, key=lambda row: int(row["word_id"]))


def _write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _groups(rows: list[dict[str, str]]) -> list[str]:
    parents = list(range(len(rows)))

    def root(index: int) -> int:
        while index != parents[index]:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    seen: dict[tuple[str, str], int] = {}
    for index, row in enumerate(rows):
        keys = [("game", _game_key(row["word"]))]
        if row.get("family", "").strip():
            keys.append(("family", _lexeme(row["family"].strip())))
        for key in keys:
            if key in seen:
                left, right = root(index), root(seen[key])
                parents[max(left, right)] = min(left, right)
            else:
                seen[key] = index
    return [f"g{rows[root(index)]['word_id']}" for index in range(len(rows))]


def _frequencies(path: Path | None) -> dict[str, float]:
    frequencies: dict[str, float] = {}
    if path is None:
        return frequencies
    for row in _read_csv(path, {"word", "frequency"}):
        word = _lexeme(row["word"])
        if not word.strip() or word in frequencies:
            raise ValueError("Frequency words must be nonempty and unique after normalization")
        value = float(row["frequency"])
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Frequency must be finite and between 0 and 1")
        frequencies[word] = value
    return frequencies


class _DefinitionText(HTMLParser):
    """Prefer DEX definition spans; never mistake full-page navigation for evidence."""

    _VOID = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
    _BLOCK = {"p", "div", "br", "li", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[tuple[str, set[str]]] = []
        self.tree: list[list[str]] = []
        self.raw: list[list[str]] = []
        self.active: list[str] | None = None
        self.capture_depth = 0
        self.full_page = False

    def handle_starttag(self, tag: str, attrs) -> None:
        classes = set((dict(attrs).get("class") or "").split())
        self.full_page |= tag in {"html", "body"}
        if tag not in self._VOID:
            self.stack.append((tag, classes))
        if self.active is None and tag == "span":
            target = None
            if "tree-def" in classes:
                target = self.tree
            elif "def" in classes and any("defWrapper" in item[1] for item in self.stack):
                target = self.raw
            if target is not None:
                self.active = []
                target.append(self.active)
                self.capture_depth = len(self.stack)
        if tag in self._BLOCK:
            self.handle_data(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK:
            self.handle_data(" ")
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if self.active is not None and len(self.stack) < self.capture_depth:
            self.active = None

    def handle_data(self, data: str) -> None:
        if any(tag in {"script", "style"} for tag, _ in self.stack):
            return
        self.parts.append(data)
        if self.active is not None:
            self.active.append(data)

    def text(self) -> str:
        definitions = self.tree or self.raw
        raw = (
            " ".join("".join(parts) for parts in definitions)
            if definitions
            else ""
            if self.full_page
            else "".join(self.parts)
        )
        return " ".join(raw.split())


def _dictionary(cache: Path | None, wanted_keys: set[str]) -> tuple[dict, dict]:
    indexed: dict[str, list[dict]] = {}
    hashes = {}
    if cache is None:
        return indexed, {}
    if not cache.is_dir():
        raise ValueError(f"DEX cache is not a directory: {cache}")
    for path in sorted(cache.glob("*.json")):
        source = path.read_bytes()
        payload = json.loads(source)
        if not isinstance(payload, dict) or any(
            not isinstance(payload.get(field), str)
            for field in ("word", "original", "status", "html")
        ):
            raise ValueError(f"{path}: invalid DEX cache record")
        if not payload["original"].strip() or not payload["status"].strip():
            raise ValueError(f"{path}: DEX original and status must be nonempty")
        if _game_key(payload["word"]) != _game_key(payload["original"]):
            raise ValueError(f"{path}: DEX word key disagrees with original spelling")
        key = _game_key(payload["original"])
        if key in wanted_keys:
            text, status = _extract_definition(payload)
            indexed.setdefault(key, []).append(
                {"original": payload["original"], "definition": text, "status": status}
            )
        hashes[path.name] = hashlib.sha256(source).hexdigest()
    return indexed, {
        "dex_file_count": len(hashes),
        "dex_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
    }


def _definition(word: str, dictionary: dict) -> tuple[str, str]:
    candidates = dictionary.get(_game_key(word), [])
    exact = [item for item in candidates if _lexeme(item["original"]) == _lexeme(word)]
    if len(exact) != 1:
        return "", "ambiguous" if candidates else "missing"
    return exact[0]["definition"], exact[0]["status"]


def _extract_definition(item: dict) -> tuple[str, str]:
    if item["status"] != "ok":
        return "", item["status"]
    parser = _DefinitionText()
    parser.feed(item["html"])
    parser.close()
    text = parser.text()
    return text, "ok" if text else "empty"


def prepare_dataset(
    vocabulary_csv: Path,
    output_dir: Path,
    *,
    source_version: str,
    seed: int = 0,
    dex_cache: Path | None = None,
    frequencies_csv: Path | None = None,
) -> dict:
    """Freeze authoritative entries, blind labels and evidence without model/DB I/O."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"Dataset output already exists: {output_dir}")
    if not isinstance(source_version, str) or not source_version.strip():
        raise ValueError("source_version must be nonempty")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    rows = _vocabulary(vocabulary_csv)
    for row, group in zip(rows, _groups(rows)):
        row["game_key"] = _game_key(row["word"])
        row["group"] = group
        bucket = int(hashlib.sha256(f"{seed}:{row['group']}".encode()).hexdigest(), 16) % 4
        row["split"] = ("dev", "calibration", "test", "test")[bucket]
        row["level"] = ""
    frequencies = _frequencies(frequencies_csv)
    evidence = [
        dict(
            word_id=row["word_id"],
            frequency=frequencies.get(_lexeme(row["word"]), ""),
            frequency_present=str(_lexeme(row["word"]) in frequencies).lower(),
            definition="",
            definition_status="missing",
        )
        for row in rows
    ]
    dictionary, dictionary_inputs = _dictionary(dex_cache, {row["game_key"] for row in rows})
    for row, item in zip(rows, evidence):
        item["definition"], item["definition_status"] = _definition(row["word"], dictionary)
    inputs = {"vocabulary_sha256": _sha256(vocabulary_csv), **dictionary_inputs}
    if frequencies_csv:
        inputs["frequencies_sha256"] = _sha256(frequencies_csv)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{output_dir.name}-", dir=output_dir.parent) as temporary:
        staged = Path(temporary) / "dataset"
        staged.mkdir()
        paths = {name: staged / f"{name}.csv" for name in ("vocabulary", "evidence", "labels")}
        _write_csv(
            paths["vocabulary"], ["word_id", "word", "type", "game_key", "group", "split"], rows
        )
        _write_csv(
            paths["evidence"],
            ["word_id", "frequency", "frequency_present", "definition", "definition_status"],
            evidence,
        )
        _write_csv(paths["labels"], ["word_id", "word", "type", "group", "split", "level"], rows)
        manifest = {
            "schema_version": 1,
            "source_version": source_version,
            "seed": seed,
            "inputs": inputs,
            "artifacts": {path.name: _sha256(path) for path in paths.values()},
        }
        paths["manifest"] = staged / "manifest.json"
        paths["manifest"].write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if output_dir.exists() or output_dir.is_symlink():
            raise FileExistsError(f"Dataset output already exists: {output_dir}")
        staged.rename(output_dir)
    return {**{name: output_dir / path.name for name, path in paths.items()}, "count": len(rows)}
