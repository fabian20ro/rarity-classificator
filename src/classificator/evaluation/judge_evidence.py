"""Project every existing curated form context into label-free judge evidence."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ..models import BaseWordRow
from .chat_judge import _evidence
from .dataset import _read_csv, _sha256, _write_csv
from .exact_form import RUBRIC_ID, load_form_contract
from .form_evidence_audit import _check_export


def merge_judge_evidence(evidence_csv, form_contract_dir, output_dir, *, projection_csv=None):
    """Preserve lexical senses; append curated POS/meanings, with separate provenance.

    Curated contexts may have been written after seeing pilot labels. This export
    is label-free, not independent evidence or a claim of human validation.
    Illustrative examples are excluded: they are not corpus attestations.
    """
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    manifest = _check_export(form_contract_dir, {"forms.csv"})
    if manifest.get("rubric") != RUBRIC_ID:
        raise ValueError("Unsupported form rubric")
    rows = _read_csv(evidence_csv, {"word_id", "word", "evidence_json"})
    items = [BaseWordRow(int(r["word_id"]), r["word"], "N") for r in rows]
    evidence = _evidence(evidence_csv, items)
    contracts = load_form_contract(
        form_contract_dir / "forms.csv", {i.word_id: i.word for i in items}
    )
    definitions = {}
    if projection_csv is not None:
        fields = {"word_id", "word", "context_id", "pos", "original_meaning", "definition"}
        originals = {
            (str(wid), c["context_id"]): (form["word"], c)
            for wid, form in contracts.items()
            for c in form["contexts"]
        }
        for row in _read_csv(projection_csv, fields):
            key = (row["word_id"], row["context_id"])
            if set(row) != fields or key in definitions or key not in originals:
                raise ValueError("Projection schema/identity mismatch")
            word, context = originals[key]
            if (
                row["word"] != word
                or row["pos"] != context["pos"]
                or row["original_meaning"] != context["meaning"]
                or not row["definition"].strip()
            ):
                raise ValueError("Projection must preserve original identity/POS/meaning")
            definitions[key] = row["definition"]
        if set(definitions) != set(originals):
            raise ValueError("Projection must cover every curated context")
    provenance, changed = [], 0
    for item in items:
        value = evidence[item.word_id]
        contexts = contracts[item.word_id]["contexts"]
        changed += bool(contexts)
        for context in contexts:
            sense = dict(
                pos=context["pos"],
                definition=definitions.get(
                    (str(item.word_id), context["context_id"]), context["meaning"]
                ),
                number_restriction="",
                grammar=[],
                context=[],
                context_incomplete=False,
                usage_labels=[],
            )
            if sense not in value["senses"]:
                value["senses"].append(sense)
            value["valid_pos"] = sorted(set(value["valid_pos"]) | {sense["pos"]})
            digest = hashlib.sha256(
                json.dumps(sense, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest()
            provenance.append(
                dict(
                    word_id=item.word_id,
                    word=item.word,
                    context_id=context["context_id"],
                    source=context["source"],
                    original_meaning=context["meaning"],
                    projected_definition=sense["definition"],
                    projected_sense_sha256=digest,
                )
            )
    summary = dict(
        forms=len(items),
        forms_with_curated_contexts=changed,
        curated_contexts=len(provenance),
        projected_contexts_changed=sum(
            p["original_meaning"] != p["projected_definition"] for p in provenance
        ),
        with_senses=sum(bool(v["senses"]) for v in evidence.values()),
        scope="Previously curated, potentially label-exposed contexts; not independent validation",
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".judge-evidence-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        _write_csv(
            staged / "evidence.csv",
            ["word_id", "word", "evidence_json"],
            [
                dict(
                    word_id=i.word_id,
                    word=i.word,
                    evidence_json=json.dumps(evidence[i.word_id], ensure_ascii=False),
                )
                for i in items
            ],
        )
        _write_csv(
            staged / "provenance.csv",
            [
                "word_id",
                "word",
                "context_id",
                "source",
                "original_meaning",
                "projected_definition",
                "projected_sense_sha256",
            ],
            provenance,
        )
        (staged / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        receipt = dict(
            policy="curated-judge-evidence-v1",
            inputs={
                str(p.resolve()): _sha256(p)
                for p in [
                    evidence_csv,
                    form_contract_dir / "manifest.json",
                    form_contract_dir / "forms.csv",
                ]
                + ([projection_csv] if projection_csv is not None else [])
            },
            implementation={str(Path(__file__).resolve()): _sha256(Path(__file__))},
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
        staged.rename(output_dir)
    return summary
