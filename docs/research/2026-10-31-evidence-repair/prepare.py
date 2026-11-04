"""Offline regeneration and outcome-blind bounded selection. Never reads gold scores."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from classificator.evaluation.audit_judge_evidence import export_audit_judge_evidence
from classificator.evaluation.dataset import _sha256, _write_csv
from classificator.evaluation.form_evidence_audit import audit_form_evidence, FORM_FIELDS
from classificator.evaluation.judge_evidence import merge_judge_evidence
from classificator.evaluation.local_evidence import export_local_evidence


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def evidence(path):
    return {r["word_id"]: json.loads(r["evidence_json"]) for r in read(path)}


def semantic(value):
    return dict(
        valid_pos=sorted(value["valid_pos"]),
        senses=sorted(
            [
                json.dumps(
                    {k: v for k, v in s.items() if k != "form_relation"},
                    sort_keys=True,
                    ensure_ascii=False,
                )
                for s in value["senses"]
            ]
        ),
    )


def prepare(base, out):
    out.mkdir(parents=True, exist_ok=False)
    campaign = base / "1000-judges-2026-10-31"
    protected = json.loads((campaign / "qwen/protected-inputs.json").read_text())
    # Snapshot references as bytes; this stage never parses scores.
    for folder in ("review50-2026-10-31", "gpt-judge-2026-10-31/inputs"):
        protected.update({str(p): _sha256(p) for p in (base / folder).rglob("*") if p.is_file()})
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    (out / "protected-inputs.json").write_text(json.dumps(protected, indent=2) + "\n")
    pilot = base / "local-fallback-2026-10-25/inputs-final"
    contract = base / "exact-form-evaluation-2026-10-21-v2/forms"
    new = base / "independent-evidence-2026-10-30/inputs"
    with (
        patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
    ):
        export_local_evidence(
            pilot / "inventory.csv",
            pilot / "loc.txt",
            base / "lexical-variants-2026-10-28/sources.csv",
            pilot / "mentions.csv",
            out / "pilot-lexical",
        )
        forms = []
        for row in read(contract / "forms.csv"):
            forms.append(
                dict(
                    form_id=row["word_id"],
                    word=row["word"],
                    group="pilot",
                    inventory_ids_json=json.dumps([int(row["word_id"])]),
                    inventory_types_json=json.dumps([row["inventory_type"]]),
                    loc_pos_json=json.dumps(
                        sorted({e["pos"] for e in json.loads(row["loc_entries"])})
                    ),
                    selection_slice="existing150",
                    selection_reason="unchanged pilot membership",
                )
            )
        _write_csv(out / "pilot-forms.csv", sorted(FORM_FIELDS), forms)
        audit_form_evidence(
            out / "pilot-forms.csv",
            pilot / "inventory.csv",
            out / "pilot-lexical",
            contract,
            out / "pilot-audit",
        )
        export_audit_judge_evidence(
            out / "pilot-forms.csv",
            pilot / "inventory.csv",
            out / "pilot-audit",
            out / "pilot-source",
        )
        merge_judge_evidence(
            out / "pilot-source/evidence.csv",
            contract,
            out / "pilot-corrected",
            projection_csv=base / "qwen-judge-curated-2026-10-30/projection.csv",
        )
        export_local_evidence(
            new / "inventory.csv",
            new / "loc.txt",
            new / "sources.csv",
            new / "mentions.csv",
            out / "new-lexical",
        )
        audit_form_evidence(
            new / "forms.csv",
            base.parent / "rarity/step1_words.csv",
            out / "new-lexical",
            base / "independent-evidence-2026-10-30/run-final/form-contract",
            out / "new-audit",
        )
        export_audit_judge_evidence(
            new / "forms.csv", new / "vocabulary.csv", out / "new-audit", out / "new-corrected"
        )
    old_paths = {
        "pilot150": base / "gpt-judge-2026-10-31/inputs/evidence.csv",
        "review50": campaign / "gpt/inputs/evidence.csv",
    }
    new_paths = {
        "pilot150": out / "pilot-corrected/evidence.csv",
        "review50": out / "new-corrected/evidence.csv",
    }
    vocab_paths = {
        "pilot150": base / "gpt-judge-2026-10-31/inputs/vocabulary.csv",
        "review50": campaign / "gpt/inputs/vocabulary.csv",
    }
    review_ids = {r["word_id"] for r in read(campaign / "final-routing/review-queue.csv")}
    rows, old_all, new_all = [], {}, {}
    for cohort in old_paths:
        old, corrected = evidence(old_paths[cohort]), evidence(new_paths[cohort])
        for r in read(vocab_paths[cohort]):
            wid = r["word_id"]
            if cohort == "review50" and wid not in review_ids:
                continue
            assert wid not in old_all and wid in corrected
            old_all[wid], new_all[wid] = old[wid], corrected[wid]
            rows.append(
                dict(
                    word_id=wid,
                    word=r["word"],
                    type=r["type"],
                    cohort=cohort,
                    semantic_changed=int(semantic(old[wid]) != semantic(corrected[wid])),
                    old_senses=len(old[wid]["senses"]),
                    new_senses=len(corrected[wid]["senses"]),
                    missing_pos="|".join(corrected[wid]["missing_definition_pos"]),
                )
            )
    _write_csv(out / "evidence-diff.csv", list(rows[0]), rows)
    # Diagnostic sentinels were discussed before this experiment; no unbiased claim.
    sentinels = {"otel", "pustnici", "ozene", "ceruit", "tunet"}
    selected = [dict(r, selection="documented_sentinel") for r in rows if r["word"] in sentinels]
    rank = lambda r: hashlib.sha256(("evidence-repair-v1:" + r["word_id"]).encode()).hexdigest()
    remaining = sorted([r for r in rows if r["word"] not in sentinels], key=rank)
    # Up to 15 content changes: 8 pilot, 7 review; fill unused quota deterministically.
    changed = []
    for cohort, quota in [("pilot150", 8), ("review50", 7)]:
        changed.extend(
            [r for r in remaining if r["cohort"] == cohort and r["semantic_changed"]][:quota]
        )
    changed += [r for r in remaining if r["semantic_changed"] and r not in changed][
        : 15 - len(changed)
    ]
    selected += [dict(r, selection="content_change") for r in changed]
    # Ten repeat controls, five per cohort: identical OLD payload in both arms.
    for cohort in ("pilot150", "review50"):
        selected += [
            dict(r, selection="identical_repeat_control")
            for r in remaining
            if r["cohort"] == cohort and not r["semantic_changed"]
        ][:5]
    assert len(selected) <= 30 and len({r["word_id"] for r in selected}) == len(selected)
    selected.sort(key=rank)
    _write_csv(out / "selection.csv", list(selected[0]), selected)
    for arm in ("old", "corrected"):
        folder = out / arm / "inputs"
        folder.mkdir(parents=True)
        _write_csv(
            folder / "vocabulary.csv",
            ["word_id", "word", "type"],
            [{k: r[k] for k in ("word_id", "word", "type")} for r in selected],
        )
        _write_csv(
            folder / "evidence.csv",
            ["word_id", "word", "evidence_json"],
            [
                dict(
                    word_id=r["word_id"],
                    word=r["word"],
                    evidence_json=json.dumps(
                        old_all[r["word_id"]]
                        if arm == "old" or r["selection"] == "identical_repeat_control"
                        else new_all[r["word_id"]],
                        ensure_ascii=False,
                    ),
                )
                for r in selected
            ],
        )
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    print(
        json.dumps(
            dict(
                forms=len(rows),
                selected=len(selected),
                changes={
                    c: sum(r["semantic_changed"] for r in rows if r["cohort"] == c)
                    for c in old_paths
                },
                protected=len(protected),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.base.resolve(), args.output.resolve())
