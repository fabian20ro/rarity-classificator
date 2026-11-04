"""Replay the frozen audit policy offline; preserve all prior scores and artifacts."""

import argparse
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from classificator.evaluation.dataset import _sha256
from classificator.evaluation.human_acceptance import audit_human_acceptance


def read(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def run(policy, output):
    config = json.loads(policy.read_text())
    package = Path(config["sources"]["package_manifest"]["path"]).parent
    previous = package.parent
    protected = json.loads((previous / "protected-inputs.json").read_text())
    protected.update({str(p): _sha256(p) for p in previous.rglob("*") if p.is_file()})
    for path, digest in protected.items():
        assert _sha256(Path(path)) == digest, path
    with (
        patch("subprocess.Popen", side_effect=AssertionError("Processes forbidden")),
        patch("subprocess.run", side_effect=AssertionError("Processes forbidden")),
        patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")),
        patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
    ):
        report = audit_human_acceptance(policy, output)
        assert report["human_policy_satisfied"]
        assert report["scope"] == dict(correction_rows=165, guard_rows=233, human_references=200)
        assert report["unchanged_inventory_rows"] == 77533
        assert report["inverse_restores_snapshot"]
        assert not report["legacy_gate"]["passed"]
        assert not report["upload_authorized"] and not report["rollback_authorized"]
        assert read(output / "candidate-issues.csv") == []
        assert all(r["satisfied"] == "True" for r in read(output / "criteria.csv"))
        assert (output / "changes.csv").read_bytes() == (package / "corrections.csv").read_bytes()
        # Independently compare the frozen candidate's delta with the human-only package.
        before = {r["word_id"]: r for r in read(Path(config["sources"]["snapshot"]["path"]))}
        after = {r["word_id"]: r for r in read(Path(config["sources"]["candidate"]["path"]))}
        changed = {i for i in before if before[i] != after[i]}
        changes = read(package / "corrections.csv")
        assert set(before) == set(after) and changed == {r["live_word_id"] for r in changes}
        assert len(changed) == 165
        for r in changes:
            assert after[r["live_word_id"]]["rarity_level"] == r["target_level"]
            assert before[r["live_word_id"]]["rarity_level"] == r["expected_level"]
        with TemporaryDirectory() as temp:
            replay = Path(temp) / "audit"
            audit_human_acceptance(policy, replay)
            artifact_names = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
            assert artifact_names == {
                str(p.relative_to(replay)) for p in replay.rglob("*") if p.is_file()
            }
            for name in artifact_names:
                assert (output / name).read_bytes() == (replay / name).read_bytes(), name
    for path, digest in protected.items():
        assert _sha256(Path(path)) == digest, path
    verification = dict(
        protected_files_unchanged=len(protected),
        byte_identical_replay_files=len(artifact_names),
        independently_reconciled_corrections=165,
        human_references_preserved=200,
        database_reads=0,
        database_writes=0,
        model_calls=0,
        upload_entrypoint_invoked=False,
        snapshot_captured_at=json.loads((previous / "snapshot-provenance.json").read_text())[
            "captured_at"
        ],
    )
    (output / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
    (output / "protected-inputs.json").write_text(json.dumps(protected, indent=2) + "\n")
    verification_manifest = dict(
        inputs={str(policy.resolve()): _sha256(policy)},
        implementation={str(Path(__file__).resolve()): _sha256(Path(__file__))},
        artifacts={
            str(p.relative_to(output)): _sha256(p) for p in output.rglob("*") if p.is_file()
        },
    )
    (output / "verification-manifest.json").write_text(
        json.dumps(verification_manifest, indent=2) + "\n"
    )
    print(json.dumps(dict(report=report, verification=verification), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path(__file__).with_name("policy.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.policy.resolve(), args.output.resolve())
