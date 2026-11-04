"""Freeze exact surfaces and source-bounded POS evidence, independently of labels."""

import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _read_csv, _sha256, _vocabulary, _write_csv

RUBRIC_ID = "exact-form-most-familiar-valid-sense-v1"
CONTEXT_FIELDS = {"word_id", "word", "context_id", "pos", "meaning", "example", "source"}
FORM_FIELDS = ["word_id", "word", "inventory_type", "rubric", "coverage", "loc_entries", "contexts"]


def prepare_exact_forms(vocabulary_csv: Path, loc_file: Path, contexts_csv: Path, output_dir: Path):
    """Keep inventory identities; collect every exact LOC entry plus vetted contexts.

    Contexts are explicit lexical evidence, never arbitrary DEX search results.
    They may describe inflected uses of this surface without adding new targets.
    """
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    rows = _vocabulary(vocabulary_csv)
    forms = {
        row["word_id"]: dict(
            word_id=row["word_id"],
            word=row["word"],
            inventory_type=row["type"],
            rubric=RUBRIC_ID,
            coverage="source_bounded_not_exhaustive",
            loc_entries=[],
            contexts=[],
        )
        for row in rows
    }
    by_word = {_lexeme(row["word"]): row["word_id"] for row in rows}
    if len(by_word) != len(rows):
        raise ValueError("One target ID per exact form is required")
    for line_number, line in enumerate(loc_file.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split()
        if len(fields) < 2:
            continue
        spelling = fields[0].replace("'", "").replace("’", "")
        if fields[1].isdigit():
            match = re.search(r"([A-Z]+)$", spelling)
            if not match:
                raise ValueError(f"Unknown LOC format at line {line_number}")
            pos, spelling, morphology = match[1], spelling[: match.start()], fields[1]
        else:
            pos, morphology = fields[1], " ".join(fields[2:])
        word_id = by_word.get(_lexeme(spelling))
        if word_id is not None:
            forms[word_id]["loc_entries"].append(
                dict(pos=pos, morphology=morphology, line=line_number, entry=line.strip())
            )
    for form in forms.values():
        if not form["loc_entries"]:
            raise ValueError(f"No exact LOC entry for {form['word']!r}")
    seen = set()
    for context in _read_csv(contexts_csv, CONTEXT_FIELDS):
        if set(context) != CONTEXT_FIELDS:
            raise ValueError("Unexpected context columns; labels/estimates must stay separate")
        word_id = str(int(context["word_id"]))
        if word_id not in forms or context["word"] != forms[word_id]["word"]:
            raise ValueError("Context must match target ID and exact spelling")
        if context["context_id"] in seen or any(not value.strip() for value in context.values()):
            raise ValueError("Contexts require unique IDs and nonempty lexical fields")
        seen.add(context["context_id"])
        forms[word_id]["contexts"].append(
            {k: v for k, v in context.items() if k not in {"word_id", "word"}}
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".forms-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        exported = [
            dict(
                form,
                loc_entries=json.dumps(form["loc_entries"], ensure_ascii=False),
                contexts=json.dumps(form["contexts"], ensure_ascii=False),
            )
            for form in forms.values()
        ]
        path = staged / "forms.csv"
        _write_csv(path, FORM_FIELDS, exported)
        manifest = dict(
            schema=1,
            rubric=RUBRIC_ID,
            inputs={str(p.resolve()): _sha256(p) for p in (vocabulary_csv, loc_file, contexts_csv)},
            artifacts={"forms.csv": _sha256(path)},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return dict(forms=output_dir / "forms.csv", count=len(rows))


def load_form_contract(path: Path, inventory: dict[int, str]) -> dict[int, dict]:
    """Validate the frozen CSV boundary before it can enter model state."""
    result = {}
    for row in _read_csv(path, set(FORM_FIELDS)):
        if set(row) != set(FORM_FIELDS):
            raise ValueError("Unexpected form columns")
        word_id = int(row.pop("word_id"))
        if word_id in result or inventory.get(word_id) != row["word"]:
            raise ValueError("Form contract identity mismatch")
        if row["rubric"] != RUBRIC_ID or row["coverage"] != "source_bounded_not_exhaustive":
            raise ValueError("Unknown form contract policy")
        for key in ("loc_entries", "contexts"):
            row[key] = json.loads(row[key])
        schemas = {
            "loc_entries": {"pos", "morphology", "line", "entry"},
            "contexts": CONTEXT_FIELDS - {"word_id", "word"},
        }
        for key, fields in schemas.items():
            if not isinstance(row[key], list) or (key == "loc_entries" and not row[key]):
                raise ValueError("Invalid form evidence list")
            for entry in row[key]:
                if not isinstance(entry, dict) or set(entry) != fields:
                    raise ValueError("Unexpected form evidence fields; no labels/estimates")
                for field, value in entry.items():
                    if field == "line":
                        if type(value) is not int or value <= 0:
                            raise ValueError("Invalid LOC line")
                    elif not isinstance(value, str) or not value.strip():
                        raise ValueError("Invalid lexical evidence value")
        ids = [entry["context_id"] for entry in row["contexts"]]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate context ID")
        result[word_id] = row
    if result.keys() != inventory.keys():
        raise ValueError("Form contract must cover the complete inventory")
    return result
