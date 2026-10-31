"""Audit frozen exact forms against source-bounded lexical exports; no scoring."""

from collections import Counter
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _read_csv, _sha256, _vocabulary, _write_csv
from .local_evidence import SENSE_FIELDS, POLICY as LEXICAL_POLICY
from .exact_form import load_form_contract, RUBRIC_ID

FORM_FIELDS = {
    "form_id",
    "word",
    "group",
    "inventory_ids_json",
    "inventory_types_json",
    "loc_pos_json",
    "selection_slice",
    "selection_reason",
}
AUDIT_FIELDS = [
    "form_id",
    "word",
    "loc_pos",
    "aligned_pos",
    "missing_pos",
    "usable_pos",
    "coverage",
    "exact_senses",
    "usable_contexts",
    "unresolved_contexts",
]
CONTEXT_FIELDS = ["form_id", "context_status", "context_text", *SENSE_FIELDS]
MEMBER_FIELDS = ["form_id", "word_id", "word", "type"]


def _check_export(directory, required):
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if not required <= set(manifest.get("artifacts", {})):
        raise ValueError("Incomplete export manifest")
    if not isinstance(manifest.get("inputs"), dict) or not manifest["inputs"]:
        raise ValueError("Missing input provenance")
    for section in ("inputs", "implementation"):
        if not isinstance(manifest.get(section, {}), dict):
            raise ValueError("Invalid provenance section")
        for filename, digest in manifest.get(section, {}).items():
            path = Path(filename)
            if not path.is_file() or _sha256(path) != digest:
                raise ValueError(f"Export input/implementation hash mismatch: {path}")
    for name, digest in manifest["artifacts"].items():
        if Path(name).name != name or _sha256(directory / name) != digest:
            raise ValueError(f"Export artifact hash mismatch: {name}")
    return manifest


def _members(forms, inventory, contracts):
    by_word = {}
    for row in inventory.values():
        by_word.setdefault(_lexeme(row["word"]), []).append(row)
    seen_ids, seen_words, memberships = set(), set(), []
    for form in forms:
        wid, word = form["form_id"], form["word"]
        if set(form) != FORM_FIELDS or wid in seen_ids or _lexeme(word) in seen_words:
            raise ValueError("Duplicate form or unexpected schema")
        seen_ids.add(wid)
        seen_words.add(_lexeme(word))
        ids = json.loads(form["inventory_ids_json"])
        types = json.loads(form["inventory_types_json"])
        positions = json.loads(form["loc_pos_json"])
        expected = by_word.get(_lexeme(word), [])
        if (
            not isinstance(ids, list)
            or not ids
            or any(type(i) is not int or i <= 0 for i in ids)
            or len(set(ids)) != len(ids)
            or set(map(str, ids)) != {r["word_id"] for r in expected}
            or wid not in set(map(str, ids))
        ):
            raise ValueError("Incomplete or invalid inventory membership")
        if (
            not isinstance(types, list)
            or any(not isinstance(p, str) or not p for p in types)
            or set(types) != {r["type"] for r in expected}
            or len(types) != len(set(types))
        ):
            raise ValueError("Inventory POS mismatch")
        actual = {entry["pos"] for entry in contracts[int(wid)]["loc_entries"]}
        if (
            not isinstance(positions, list)
            or any(not isinstance(p, str) or not p for p in positions)
            or len(positions) != len(set(positions))
            or set(positions) != actual
        ):
            raise ValueError("LOC POS mismatch")
        memberships.extend(dict(form_id=wid, **row) for row in expected)
    return memberships


SCOPE_FIELDS = (
    "word_id",
    "word",
    "source_path",
    "source_sha256",
    "heading",
    "pos",
    "pos_detail",
    "source_entry_id",
    "source_dictionary",
    "variant_id",
)


def _context(sense, parents):
    texts, visited = [], set()
    current = sense
    while True:
        key = tuple(current[k] for k in SCOPE_FIELDS) + (current["sense_id"],)
        if key in visited:
            return "cyclic_parent", ""
        visited.add(key)
        if current["alignment"] != "exact":
            return "unaligned", ""
        if not current["definition"].strip() or not current["pos"]:
            return "empty_definition_or_pos", ""
        texts.append(current["definition"])
        if not current["parent_sense_id"]:
            return "usable_source_bounded", " — ".join(reversed(texts))
        matches = parents.get(key[:-1] + (current["parent_sense_id"],), [])
        if len(matches) != 1:
            return "incomplete_parent" if not matches else "ambiguous_parent", ""
        current = matches[0]


def audit_form_evidence(forms_csv, inventory_csv, lexical_dir, contract_dir, output_dir):
    """Export one coverage row per form, all memberships and source-scoped contexts."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    lexical_manifest = _check_export(
        lexical_dir, {"evidence.csv", "senses.csv", "variants.csv", "source-files.csv"}
    )
    contract_manifest = _check_export(contract_dir, {"forms.csv"})
    if (
        lexical_manifest.get("policy") != LEXICAL_POLICY
        or lexical_manifest.get("extraction_revision") != "explicit-variants-v1"
        or lexical_manifest.get("senses_schema") != 2
        or not isinstance(lexical_manifest.get("implementation"), dict)
        or not lexical_manifest["implementation"]
        or contract_manifest.get("rubric") != RUBRIC_ID
    ):
        raise ValueError("Unsupported evidence policy")
    for source in _read_csv(lexical_dir / "source-files.csv", {"path", "sha256"}):
        if _sha256(Path(source["path"])) != source["sha256"]:
            raise ValueError("Lexical source hash mismatch")
    forms = _read_csv(forms_csv, FORM_FIELDS)
    inventory = {r["word_id"]: r for r in _vocabulary(inventory_csv)}
    if not forms or any(not r["form_id"].isdigit() for r in forms):
        raise ValueError("Invalid form ID")
    contracts = load_form_contract(
        contract_dir / "forms.csv", {int(r["form_id"]): r["word"] for r in forms}
    )
    memberships = _members(forms, inventory, contracts)
    evidence_rows = _read_csv(
        lexical_dir / "evidence.csv", {"word_id", "word", "loc_pos", "aligned_pos"}
    )
    evidence = {r["word_id"]: r for r in evidence_rows}
    if len(evidence_rows) != len(evidence) or set(evidence) != {r["word_id"] for r in memberships}:
        raise ValueError("Lexical export membership mismatch")
    for member in memberships:
        if evidence[member["word_id"]]["word"] != member["word"]:
            raise ValueError("Lexical export spelling mismatch")
    senses = _read_csv(lexical_dir / "senses.csv", set(SENSE_FIELDS))
    source_words = {
        _lexeme(r["word"]) for r in _read_csv(lexical_dir / "source-files.csv", {"word"})
    }
    source_rows = _read_csv(lexical_dir / "source-files.csv", {"word", "path", "sha256"})
    source_keys = {(_lexeme(r["word"]), r["path"], r["sha256"]) for r in source_rows}
    for sense in senses:
        if (
            sense["word_id"] not in evidence
            or sense["word"] != evidence[sense["word_id"]]["word"]
            or (_lexeme(sense["word"]), sense["source_path"], sense["source_sha256"])
            not in source_keys
        ):
            raise ValueError("Sense identity/source mismatch")
    parents = {}
    for sense in senses:
        key = tuple(sense[k] for k in SCOPE_FIELDS) + (sense["sense_id"],)
        parents.setdefault(key, []).append(sense)
    audits, contexts = [], []
    for form in forms:
        wid = form["form_id"]
        entry = evidence[wid]
        required = set()
        for loc in contracts[int(wid)]["loc_entries"]:
            pos = re.sub(r"\d.*", "", loc["pos"])
            required.add({"F": "N", "M": "N", "MF": "N", "VT": "V"}.get(pos, pos))
        if required != set(filter(None, entry["loc_pos"].split("|"))):
            raise ValueError("Lexical LOC POS mismatch")
        exact = [s for s in senses if s["word_id"] == wid and s["alignment"] == "exact"]
        form_contexts = []
        for sense in (s for s in senses if s["word_id"] == wid):
            status, text = _context(sense, parents)
            form_contexts.append(
                dict(form_id=wid, context_status=status, context_text=text, **sense)
            )
        contexts.extend(form_contexts)
        usable = sum(c["context_status"] == "usable_source_bounded" for c in form_contexts)
        usable_pos = {
            c["pos"] for c in form_contexts if c["context_status"] == "usable_source_bounded"
        }
        audits.append(
            dict(
                form_id=wid,
                word=form["word"],
                loc_pos=entry["loc_pos"],
                aligned_pos=entry["aligned_pos"],
                missing_pos="|".join(sorted(required - usable_pos)),
                usable_pos="|".join(sorted(usable_pos)),
                coverage=(
                    "no_source"
                    if _lexeme(form["word"]) not in source_words
                    else "no_usable_contexts"
                    if not usable
                    else "source_bounded_not_exhaustive"
                    if required and required <= usable_pos
                    else "partial_pos"
                ),
                exact_senses=len(exact),
                usable_contexts=usable,
                unresolved_contexts=len(form_contexts) - usable,
            )
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".form-audit-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        _write_csv(staged / "form-evidence-audit.csv", AUDIT_FIELDS, audits)
        _write_csv(staged / "membership.csv", MEMBER_FIELDS, memberships)
        _write_csv(staged / "contexts.csv", CONTEXT_FIELDS, contexts)
        summary = dict(
            forms=len(forms),
            inventory_rows=len(memberships),
            coverage=dict(Counter(r["coverage"] for r in audits)),
            forms_with_usable_contexts=sum(int(r["usable_contexts"]) > 0 for r in audits),
            context_status=dict(Counter(r["context_status"] for r in contexts)),
            scope="Source-bounded lexical evidence, not exhaustive senses or score validation",
        )
        (staged / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        manifest = dict(
            policy="exact-form-evidence-audit-v1",
            inputs={
                str(p.resolve()): _sha256(p)
                for p in (
                    forms_csv,
                    inventory_csv,
                    lexical_dir / "manifest.json",
                    contract_dir / "manifest.json",
                )
            },
            implementation={str(Path(__file__).resolve()): _sha256(Path(__file__))},
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return summary
