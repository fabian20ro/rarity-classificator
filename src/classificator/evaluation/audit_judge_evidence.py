"""Project verified exact-form audit CSVs into blinded judge inputs."""

import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from ..models import BaseWordRow
from .chat_judge import _evidence
from .dataset import _read_csv, _sha256, _vocabulary, _write_csv
from .form_evidence_audit import (
    AUDIT_FIELDS,
    CONTEXT_FIELDS,
    FORM_FIELDS,
    MEMBER_FIELDS,
    SCOPE_FIELDS,
    _check_export,
    _context,
)

POS = {
    "N": "substantiv neutru",
    "F": "substantiv feminin",
    "M": "substantiv masculin",
    "MF": "substantiv masculin și feminin",
    "A": "adjectiv",
    "VT": "verb tranzitiv",
    "V": "verb",
    "P": "pronume",
    "I": "interjecție",
}
GRAMMAR = re.compile(
    r"\b(?:locuțiune adverbială|pronume interogativ|pronume nehotărât|substantivat(?: neutru| feminin| masculin)?|adverbial(?:ă)?|reflexiv|intranzitiv|tranzitiv|articulat|singular|plural)\b",
    re.I,
)


def _indexed(path, key, fields):
    rows = _read_csv(path, set(fields))
    result = {}
    for row in rows:
        ident = row[key]
        if set(row) != set(fields) or not re.fullmatch(r"[1-9][0-9]*", ident) or ident in result:
            raise ValueError("Invalid or duplicate identity/schema")
        result[ident] = row
    return result


def export_audit_judge_evidence(forms_csv, vocabulary_csv, audit_dir, output_dir):
    """Keep missing senses explicit; source provenance never enters model input."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    manifest = _check_export(
        audit_dir, {"contexts.csv", "membership.csv", "form-evidence-audit.csv"}
    )
    if manifest.get("policy") != "exact-form-evidence-audit-v1":
        raise ValueError("Unsupported audit policy")
    if not isinstance(manifest.get("implementation"), dict) or not manifest["implementation"]:
        raise ValueError("Missing implementation provenance")
    forms = _indexed(forms_csv, "form_id", FORM_FIELDS)
    vocabulary = _vocabulary(vocabulary_csv)
    audits = _indexed(audit_dir / "form-evidence-audit.csv", "form_id", AUDIT_FIELDS)
    members = _read_csv(audit_dir / "membership.csv", set(MEMBER_FIELDS))
    contexts = _read_csv(audit_dir / "contexts.csv", set(CONTEXT_FIELDS))
    if set(forms) != set(audits) or set(forms) != {r["word_id"] for r in vocabulary}:
        raise ValueError("Form/vocabulary/audit identity mismatch")
    member_ids = set()
    for member in members:
        if (
            set(member) != set(MEMBER_FIELDS)
            or member["form_id"] not in forms
            or not re.fullmatch(r"[1-9][0-9]*", member["word_id"])
            or member["word_id"] in member_ids
            or member["word"] != forms[member["form_id"]]["word"]
        ):
            raise ValueError("Invalid audit membership")
        member_ids.add(member["word_id"])
    for item in vocabulary:
        wid = item["word_id"]
        form, audit = forms[wid], audits[wid]
        group = [m for m in members if m["form_id"] == wid]
        ids, types = (
            json.loads(form["inventory_ids_json"]),
            json.loads(form["inventory_types_json"]),
        )
        positions = json.loads(form["loc_pos_json"])
        if (
            item["word"] != form["word"]
            or audit["word"] != form["word"]
            or not isinstance(ids, list)
            or any(type(i) is not int for i in ids)
            or len(set(ids)) != len(ids)
            or set(map(str, ids)) != {m["word_id"] for m in group}
            or not isinstance(types, list)
            or any(not isinstance(t, str) for t in types)
            or len(set(types)) != len(types)
            or set(types) != {m["type"] for m in group}
            or not any(m["word_id"] == wid and m["type"] == item["type"] for m in group)
            or not isinstance(positions, list)
            or not positions
            or any(not isinstance(p, str) or not p for p in positions)
        ):
            raise ValueError("Exact spelling or inventory membership mismatch")
        normalized = {re.sub(r"\d.*", "", p) for p in positions}
        normalized = {{"F": "N", "M": "N", "MF": "N", "VT": "V"}.get(p, p) for p in normalized}
        if normalized != set(filter(None, audit["loc_pos"].split("|"))):
            raise ValueError("LOC POS mismatch")
        count = sum(
            c["form_id"] == wid and c["context_status"] == "usable_source_bounded" for c in contexts
        )
        if str(count) != audit["usable_contexts"]:
            raise ValueError("Usable context count mismatch")
    sources = {}
    parents = {}
    for context in contexts:
        if (
            set(context) != set(CONTEXT_FIELDS)
            or context["form_id"] not in forms
            or context["word_id"] != context["form_id"]
            or context["word"] != forms[context["form_id"]]["word"]
        ):
            raise ValueError("Context identity/schema mismatch")
        source = Path(context["source_path"])
        if source not in sources:
            sources[source] = _sha256(source)
        if sources[source] != context["source_sha256"]:
            raise ValueError("Lexical source hash mismatch")
        key = tuple(context[k] for k in SCOPE_FIELDS) + (context["sense_id"],)
        parents.setdefault(key, []).append(context)
    rows, provenance = [], []
    for item in vocabulary:
        wid = item["word_id"]
        form, audit = forms[wid], audits[wid]
        usable = [
            c
            for c in contexts
            if c["form_id"] == wid and c["context_status"] == "usable_source_bounded"
        ]
        senses = []
        for context in usable:
            if _context(context, parents) != ("usable_source_bounded", context["context_text"]):
                raise ValueError("Unverified parent context")
            ancestor = context
            parent_texts = []
            while ancestor["parent_sense_id"]:
                key = tuple(ancestor[k] for k in SCOPE_FIELDS) + (ancestor["parent_sense_id"],)
                ancestor = parents[key][0]
                parent_texts.append(ancestor["definition"])
            tags = json.loads(context["tags"])
            if not isinstance(tags, list) or any(not isinstance(t, str) or not t for t in tags):
                raise ValueError("Invalid lexical tags")
            if (
                context["number_restriction"]
                and context["variant_number_restriction"]
                and context["number_restriction"] != context["variant_number_restriction"]
            ):
                raise ValueError("Conflicting number restrictions")
            sense = dict(
                pos=context["pos_detail"] or context["pos"],
                definition=context["definition"],
                number_restriction=context["number_restriction"]
                or context["variant_number_restriction"],
                grammar=sorted({g.lower() for tag in tags for g in GRAMMAR.findall(tag)}),
                context=list(reversed(parent_texts)),
                context_incomplete=False,
                usage_labels=sorted(set(tags)),
            )
            if sense not in senses:
                senses.append(sense)
            provenance.append(dict(context, projected_sense=json.dumps(sense, ensure_ascii=False)))
        positions = {re.sub(r"\d.*", "", p) for p in json.loads(form["loc_pos_json"])}
        if not positions <= set(POS):
            raise ValueError("Unsupported LOC POS")
        value = dict(
            coverage="source_bounded_not_exhaustive",
            valid_pos=sorted({POS[p] for p in positions} | {s["pos"] for s in senses}),
            senses=sorted(senses, key=lambda s: json.dumps(s, ensure_ascii=False, sort_keys=True)),
        )
        rows.append(
            dict(
                word_id=wid, word=form["word"], evidence_json=json.dumps(value, ensure_ascii=False)
            )
        )
    summary = dict(
        forms=len(rows),
        inventory_rows=len(members),
        with_senses=sum(bool(json.loads(r["evidence_json"])["senses"]) for r in rows),
        without_senses=sum(not json.loads(r["evidence_json"])["senses"] for r in rows),
        source_contexts=len(contexts),
        projected_contexts=len(provenance),
        excluded_contexts=len(contexts) - len(provenance),
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".audit-judge-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        _write_csv(staged / "evidence.csv", ["word_id", "word", "evidence_json"], rows)
        _evidence(
            staged / "evidence.csv",
            [BaseWordRow(int(r["word_id"]), r["word"], r["type"]) for r in vocabulary],
        )
        _write_csv(staged / "provenance.csv", [*CONTEXT_FIELDS, "projected_sense"], provenance)
        (staged / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        receipt = dict(
            policy="audited-judge-evidence-v1",
            inputs={
                str(p.resolve()): _sha256(p)
                for p in (forms_csv, vocabulary_csv, audit_dir / "manifest.json")
            },
            implementation={str(Path(__file__).resolve()): _sha256(Path(__file__))},
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
        staged.rename(output_dir)
    return summary
