"""Prepare and verify the human-only package from existing local files; no DB access."""

import argparse
from dataclasses import asdict
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from classificator.evaluation.dataset import _sha256, _write_csv
from classificator.evaluation.human_corrections import (
    prepare_human_corrections,
    verify_correction_snapshot,
)
from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.quality_audit import run_quality_audit


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def run(base, out):
    out.mkdir(parents=True, exist_ok=False)
    code = Path(__file__).resolve().parents[3]
    migration = base / "migration-dry-run-2026-11-02/analysis"
    human_export = base / "conservative-export-2026-11-01/export"
    snapshot = migration / "live-snapshot.csv"
    protected = json.loads((migration / "protected-inputs.json").read_text())
    protected.update({str(p): _sha256(p) for p in migration.parent.rglob("*") if p.is_file()})
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    (out / "protected-inputs.json").write_text(json.dumps(protected, indent=2) + "\n")
    (out / "snapshot-provenance.json").write_bytes(
        (migration / "snapshot-provenance.json").read_bytes()
    )
    with (
        patch("subprocess.run", side_effect=AssertionError("Processes forbidden")),
        patch("subprocess.Popen", side_effect=AssertionError("Processes forbidden")),
        patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
        patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
    ):
        package = out / "package"
        summary = prepare_human_corrections(migration / "plan", human_export, package)
        assert (
            summary["correction_rows"],
            summary["rollback_rows"],
            summary["guard_rows"],
            summary["reviewed_forms"],
            summary["human_references"],
        ) == (165, 165, 233, 200, 200)
        before = verify_correction_snapshot(package, snapshot, out / "check-before", phase="before")
        assert before["conditions_satisfied"] and not before["upload_authorized"]
        source = read(snapshot)
        corrections = read(package / "corrections.csv")
        rollback = read(package / "rollback.csv")
        guards = read(package / "preconditions.csv")
        original = {r["word_id"]: r for r in source}
        previous_plan = {r["live_word_id"]: r for r in read(migration / "plan/plan.csv")}
        expected = {
            i
            for i, r in previous_plan.items()
            if r["decision_source"] == "human" and r["current_level"] != r["proposed_level"]
        }
        assert len(corrections) == len({r["live_word_id"] for r in corrections}) == 165
        assert {r["live_word_id"] for r in corrections} == expected
        assert {r["live_word_id"] for r in guards} == {
            i for i, r in previous_plan.items() if r["decision_source"] == "human"
        }
        # Independent projection of unchanged original human references, no model or baseline labels.
        references = read(human_export / "references.csv")
        labels = {r["word"]: r["level"] for r in references}
        assert len(labels) == 200
        assert (package / "references.csv").read_bytes() == (
            human_export / "references.csv"
        ).read_bytes()
        for g in guards:
            row = original[g["live_word_id"]]
            assert (g["word"], g["type"], g["before_level"]) == (
                row["word"],
                row["type"],
                row["rarity_level"],
            )
            assert g["after_level"] == labels[g["word"]]
        for c, r in zip(corrections, rollback, strict=True):
            assert c["live_word_id"] == r["live_word_id"]
            assert (c["word"], c["type"]) == (r["word"], r["type"])
            assert (c["target_level"], c["expected_level"]) == (
                r["expected_level"],
                r["restore_level"],
            )
            assert c["target_level"] == labels[c["word"]]
        simulated = [dict(r) for r in source]
        index = {r["word_id"]: r for r in simulated}
        for c in corrections:
            row = index[c["live_word_id"]]
            assert (row["word"], row["type"], row["rarity_level"]) == (
                c["word"],
                c["type"],
                c["expected_level"],
            )
            row["rarity_level"] = c["target_level"]
        after_csv = out / "simulation-after.csv"
        _write_csv(after_csv, list(source[0]), simulated)
        assert {i for i in original if original[i] != index[i]} == expected
        after = verify_correction_snapshot(package, after_csv, out / "check-after", phase="after")
        assert (
            after["conditions_satisfied"]
            and not after["apply_receipt_verified"]
            and not after["rollback_authorized"]
        )
        # Inverse proof on a private copy only; not a receipt that anything was applied in DB.
        for r in rollback:
            row = index[r["live_word_id"]]
            assert row["rarity_level"] == r["expected_level"]
            row["rarity_level"] = r["restore_level"]
        restored = out / "simulation-restored.csv"
        _write_csv(restored, list(source[0]), simulated)
        assert restored.read_bytes() == snapshot.read_bytes()
        restored_check = verify_correction_snapshot(
            package, restored, out / "check-restored", phase="before"
        )
        assert restored_check["conditions_satisfied"]
        with TemporaryDirectory(dir=out) as tmp:
            replay = Path(tmp)
            prepare_human_corrections(migration / "plan", human_export, replay / "package")
            for name, path, phase in (
                ("check-before", snapshot, "before"),
                ("check-after", after_csv, "after"),
                ("check-restored", restored, "before"),
            ):
                verify_correction_snapshot(package, path, replay / name, phase=phase)
            for name in ("package", "check-before", "check-after", "check-restored"):
                assert {p.name for p in (out / name).iterdir()} == {
                    p.name for p in (replay / name).iterdir()
                }
                for p in (replay / name).iterdir():
                    assert p.read_bytes() == (out / name / p.name).read_bytes(), p.name
        # Keep the legacy gate and its full-inventory denominators; no Step4 invocation here.
        quality = asdict(
            run_quality_audit(
                candidate_csv=after_csv,
                reference_csv=snapshot,
                anchor_l1_file=code / "docs/rarity-anchor-l1-ro.txt",
                min_l1_jaccard=0.7,
                min_anchor_l1_precision=0.8,
                min_anchor_l1_recall=0.8,
                repo=RunCsvRepository(),
            )
        )
        assert not quality["passed"]
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    report = dict(
        summary=summary,
        before=before,
        simulated_after=after,
        simulated_restored=restored_check,
        quality_on_full_shadow_inventory=quality,
        original_rows_unchanged=len(source) - len(corrections),
        correction_ids_independently_reconciled=165,
        original_human_references_preserved=200,
        inverse_restores_snapshot_bytes=True,
        replay_byte_identical_artifacts=16,
        protected_files_unchanged=len(protected),
        database_reads=0,
        database_writes=0,
        model_calls=0,
        upload_entrypoint_invoked=False,
        apply_receipt_exists=False,
        snapshot_captured_at=json.loads((out / "snapshot-provenance.json").read_text())[
            "captured_at"
        ],
        caveat="Prepared files and offline simulations only. No freshness, execution or rollback authorization; unchanged uploader gate remains mandatory.",
    )
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    receipt = dict(
        implementation={str(Path(__file__).resolve()): _sha256(Path(__file__))},
        inputs={
            str(snapshot): _sha256(snapshot),
            str(migration / "plan/manifest.json"): _sha256(migration / "plan/manifest.json"),
            str(human_export / "manifest.json"): _sha256(human_export / "manifest.json"),
        },
        artifacts={str(p.relative_to(out)): _sha256(p) for p in out.rglob("*") if p.is_file()},
    )
    (out / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ("before", "simulated_after", "simulated_restored")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.base.resolve(), args.output.resolve())
