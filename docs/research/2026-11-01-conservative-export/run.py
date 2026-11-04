"""Build a separate conservative inventory export from immutable local sources."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from unittest.mock import patch

from classificator.evaluation.conservative_export import export_conservative_inventory, POLICY
from classificator.evaluation.dataset import _sha256, _write_csv
from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.quality_audit import run_quality_audit


def run(base, out):
    out.mkdir(parents=True, exist_ok=False)
    code = Path(__file__).resolve().parents[3]
    original = (
        base / "pilot-2026-10-17/data/evaluations/2026-10-21-fabian-short/working-reference-150.csv"
    )
    assert _sha256(original) == _sha256(base / "gpt-judge-2026-10-31/inputs/reference.csv")
    inventory = base.parent / "rarity/step1_words.csv"
    baseline = base / "offline-wordfreq-2026-10-24/export"
    reference_snapshot = base.parent / "rarity/reference/current_db_levels.csv"
    anchors = code / "docs/rarity-anchor-l1-ro.txt"
    protected = json.loads((base / "reduction-gate-2026-11-01/protected-inputs.json").read_text())
    for path in (base / "reduction-gate-2026-11-01").rglob("*"):
        if path.is_file():
            protected[str(path)] = _sha256(path)
    references = [
        ("human_pilot150", original),
        ("human_review50", base / "review50-2026-10-31/review-responses.csv"),
    ]
    observations = [
        ("gpt_pilot150", base / "gpt-judge-2026-10-31/campaign/predictions.csv"),
        ("gpt_new1000", base / "1000-judges-2026-10-31/gpt/campaign/predictions.csv"),
        ("qwen_pilot150", base / "qwen-judge-curated-2026-10-30/campaign/predictions.csv"),
        ("qwen_conflicts31", base / "1000-judges-2026-10-31/qwen/campaign/predictions.csv"),
    ]
    for name, values in [
        ("reference-sources.csv", references),
        ("observation-sources.csv", observations),
    ]:
        _write_csv(
            out / name,
            ["source_id", "path", "sha256"],
            [dict(source_id=sid, path=str(path), sha256=_sha256(path)) for sid, path in values],
        )
    for path in [
        inventory,
        original,
        reference_snapshot,
        anchors,
        *[p for _, p in references + observations],
        *(baseline.iterdir()),
    ]:
        if path.is_file():
            protected[str(path)] = _sha256(path)
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    (out / "protected-inputs.json").write_text(json.dumps(protected, indent=2) + "\n")
    protocol = dict(
        policy=POLICY,
        baseline=str(baseline),
        inventory=str(inventory),
        human_references=200,
        reference_priority="Final working150 and imported completed review50; no inferred updates or relabelling",
        observations="Original complete GPT150+1000 and curated Qwen150+targeted31; never later selective repeats, no vote or averaging",
        quality=dict(
            reference_snapshot=str(reference_snapshot),
            reference_sha256=_sha256(reference_snapshot),
            anchors=str(anchors),
            anchors_sha256=_sha256(anchors),
            min_l1_jaccard=0.7,
            min_anchor_precision=0.8,
            min_anchor_recall=0.8,
            scope="Existing local snapshot and seed anchors, not freshly queried DB or upload authorization",
        ),
        inputs={
            str(p): _sha256(p)
            for p in [
                out / "reference-sources.csv",
                out / "observation-sources.csv",
                out / "protected-inputs.json",
            ]
        },
        implementation={
            str(p): _sha256(p)
            for p in [
                Path(__file__).resolve(),
                code / "src/classificator/evaluation/conservative_export.py",
            ]
        },
    )
    (out / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    with (
        patch("subprocess.run", side_effect=AssertionError("LLM/process forbidden")),
        patch("subprocess.Popen", side_effect=AssertionError("LLM/process forbidden")),
        patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
        patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
    ):
        summary = export_conservative_inventory(
            inventory,
            baseline,
            out / "reference-sources.csv",
            out / "observation-sources.csv",
            out / "export",
        )
        assert summary["human_forms"] == 200 and summary["human_references"] == 200
        quality = run_quality_audit(
            candidate_csv=out / "export/candidate.csv",
            reference_csv=reference_snapshot,
            anchor_l1_file=anchors,
            min_l1_jaccard=0.7,
            min_anchor_l1_precision=0.8,
            min_anchor_l1_recall=0.8,
            repo=RunCsvRepository(),
        )
        # Snapshot audit is descriptive. Even a pass is not authorization or live DB validation.
        baseline_quality = run_quality_audit(
            candidate_csv=baseline / "scores.csv",
            reference_csv=reference_snapshot,
            anchor_l1_file=anchors,
            min_l1_jaccard=0.7,
            min_anchor_l1_precision=0.8,
            min_anchor_l1_recall=0.8,
            repo=RunCsvRepository(),
        )
        quality_report = dict(
            candidate=asdict(quality),
            baseline=asdict(baseline_quality),
            scope=protocol["quality"],
            upload_authorized=False,
        )
        (out / "quality.json").write_text(json.dumps(quality_report, indent=2) + "\n")
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    report = dict(
        summary=summary,
        quality=quality_report,
        protected_files_unchanged=len(protected),
        model_calls=0,
        database_writes=0,
        protocol_sha256=_sha256(out / "protocol.json"),
        export_manifest_sha256=_sha256(out / "export/manifest.json"),
    )
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.base.resolve(), args.output.resolve())
