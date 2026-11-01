"""Freeze a single offline policy and label-free inputs before comparison."""

import argparse
import datetime
import json
from pathlib import Path

from classificator.evaluation.dataset import _read_csv, _sha256, _write_csv
from classificator.evaluation.form_evidence_audit import _check_export
from classificator.evaluation.reduction_gate import POLICY


def read(path):
    return _read_csv(path, set())


def freeze(base, out):
    out.mkdir(parents=True, exist_ok=False)
    previous = base / "evidence-repair-2026-10-31-v3"
    protected = json.loads((previous / "protected-inputs.json").read_text())
    for directory in ("evidence-repair-2026-10-31-v2", "evidence-repair-2026-10-31-v3"):
        for path in (base / directory).rglob("*"):
            if path.is_file() and path.suffix in (".csv", ".json"):
                protected[str(path)] = _sha256(path)
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    (out / "protected-inputs.json").write_text(json.dumps(protected, indent=2) + "\n")
    campaign = base / "1000-judges-2026-10-31"
    evidence_base = base / "evidence-repair-2026-10-31-v2"
    review_ids = {r["word_id"] for r in read(campaign / "final-routing/review-queue.csv")}
    cohorts = {
        "pilot150": dict(
            baseline=campaign / "pilot-policy/baseline.csv",
            gpt=campaign / "pilot-policy/gpt.csv",
            lexical=evidence_base / "pilot-corrected",
            groups=base / "gpt-judge-2026-10-31/inputs/folds.csv",
        ),
        "review50": dict(
            baseline=campaign / "comparison-inputs/baseline.csv",
            gpt=campaign / "comparison-inputs/gpt.csv",
            lexical=evidence_base / "new-corrected",
            groups=base / "independent-1000-2026-10-30/forms.csv",
        ),
    }
    source_paths = [campaign / "final-routing/review-queue.csv"]
    for cohort, paths in cohorts.items():
        _check_export(paths["lexical"], {"evidence.csv", "provenance.csv"})
        folder = out / cohort / "inputs"
        folder.mkdir(parents=True)
        selected = (
            {r["word_id"] for r in read(paths["baseline"])} if cohort == "pilot150" else review_ids
        )
        assert len(selected) == (150 if cohort == "pilot150" else 50)
        for key, columns in [
            ("baseline", ["word_id", "word", "baseline_level"]),
            ("gpt", ["word_id", "word", "status", "rarity_level"]),
            ("evidence", ["word_id", "word", "evidence_json"]),
        ]:
            source = paths["lexical"] / "evidence.csv" if key == "evidence" else paths[key]
            rows = [{k: r[k] for k in columns} for r in read(source) if r["word_id"] in selected]
            assert len(rows) == len(selected) and {r["word_id"] for r in rows} == selected
            _write_csv(folder / (key + ".csv"), columns, rows)
            source_paths.append(source)
        group_rows = []
        for r in read(paths["groups"]):
            wid = r.get("word_id", r.get("form_id"))
            if wid in selected:
                group_rows.append(dict(word_id=wid, group=r["group"], fold=r.get("fold", "")))
        assert len(group_rows) == len(selected)
        _write_csv(folder / "groups.csv", ["word_id", "group", "fold"], group_rows)
        source_paths += [paths["groups"], paths["lexical"] / "manifest.json"]
    for corpus in ("fineweb-2026-10-26", "corola-2026-10-28"):
        source_paths += [
            base / corpus / "source" / n
            for n in ("manifest.json", "frequencies.csv", "vocabulary.csv")
        ]
    code = Path(__file__).resolve().parents[3]
    protocol = dict(
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        policy=POLICY,
        primary="Accept only GPT reductions>=2 with lexical support AND (FineWeb2 support OR CoRoLa>=5). Every other row retains its frozen baseline; no increases or one-level changes.",
        methods=[
            "baseline_level",
            "gpt_full_level",
            "ungated_reduction_level",
            "lexical_only_level",
            "corpus_only_level",
            "candidate_level",
        ],
        primary_metric="Severe abs(error)>=2; excess max(abs(error)-1,0). Compare pilot150 and risk-selected50 separately, reference4 and5 separately, plus reduction-eligible subset. No pooling.",
        decision="Candidate must reduce severe count and not increase excess vsbaseline in BOTH cohorts, without worsening severe/excess in reference4 or5 of either cohort. Even a pass is development evidence only, not DB promotion.",
        groups="No fitting, threshold search or CV claim. Use existing pilot family/fold assignments and new sample groups; report family-balanced metrics, per-fold pilot counts and family overlap.",
        labels="Never consumed by gate. Human references read only after both decision CSVs exist. Previous150 reused development;50 now also development, risk-selected. No further human round.",
        evidence_limit="Exact orthography counts aggregate homographs/POS and may contain noise. Support is attestation, not commonness. No inferred sense frequencies.",
        source_usage="CoRoLa published frequency list, existing local noncommercial research permission; no new downloads or public per-form count redistribution.",
        source_inputs={str(p): _sha256(p) for p in source_paths},
        frozen={
            str(p): _sha256(p)
            for p in [
                *out.glob("*/inputs/*.csv"),
                out / "protected-inputs.json",
                Path(__file__),
                *(code / "src/classificator/evaluation").glob("*.py"),
            ]
        },
    )
    (out / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    print(
        json.dumps(dict(output=str(out), protected=len(protected), forms=[150, 50], policy=POLICY))
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    freeze(args.base.resolve(), args.output.resolve())
