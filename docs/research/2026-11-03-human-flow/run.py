"""Offline preview plus transaction-boundary rehearsal; NEVER a PostgreSQL run."""

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from classificator.evaluation.dataset import _sha256
from classificator.human_correction_flow import run_human_corrections
from tests.test_human_correction_flow import MemoryStore
from tests.test_local_evidence import read


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    policy = here.parent / "2026-11-03-human-acceptance/policy.json"
    approval = here / "approval.json"
    config = json.loads(policy.read_text())
    package_id = json.loads(approval.read_text())["package_id"]
    previous = (
        Path(config["sources"]["candidate"]["path"]).parent.parent / "human-acceptance-2026-11-03"
    )
    protected = json.loads((previous / "protected-inputs.json").read_text())
    protected.update({str(p): _sha256(p) for p in previous.rglob("*") if p.is_file()})
    for path, digest in protected.items():
        assert _sha256(Path(path)) == digest, path
    (output / "TEST-ONLY.txt").write_text(
        "No live database. simulated-* uses a memory transaction double, including synthetic row versions. These receipts are NOT DB receipts.\n"
    )
    with (
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
        patch("subprocess.Popen", side_effect=AssertionError("Processes forbidden")),
        patch("subprocess.run", side_effect=AssertionError("Processes forbidden")),
        patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")),
        patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
    ):
        preview = run_human_corrections(approval, policy, output / "preview")
        assert preview["status"] == "dry_run" and not preview["applied"]
        run_human_corrections(approval, policy, output / "replay")
        names = [
            p.relative_to(output / "preview")
            for p in (output / "preview").rglob("*")
            if p.is_file()
        ]
        for name in names:
            assert (output / "preview" / name).read_bytes() == (
                output / "replay" / name
            ).read_bytes(), name
        source = read(Path(config["sources"]["snapshot"]["path"]))
        store = MemoryStore(source)
        applied = run_human_corrections(
            approval,
            policy,
            output / "simulated-apply",
            action="apply",
            store=store,
            confirm_package=package_id,
        )
        assert applied["status"] == "applied"
        expected = {r["word_id"]: r for r in read(Path(config["sources"]["candidate"]["path"]))}
        assert {
            i: {k: v for k, v in row.items() if k != "version"} for i, row in store.rows.items()
        } == expected
        assert len(store.receipts[package_id]["changed_ids"]) == 165
        recovered = run_human_corrections(
            approval,
            policy,
            output / "simulated-retry",
            action="apply",
            store=store,
            confirm_package=package_id,
        )
        assert recovered["status"] == "already_applied"
        rollback = run_human_corrections(
            approval,
            policy,
            output / "simulated-rollback",
            action="rollback",
            store=store,
            confirm_package=package_id,
        )
        assert rollback["status"] == "rolled_back"
        assert {
            i: {k: v for k, v in row.items() if k != "version"} for i, row in store.rows.items()
        } == {r["word_id"]: r for r in source}
    for path, digest in protected.items():
        assert _sha256(Path(path)) == digest, path
    report = dict(
        version="human-corrections-flow-v1",
        policy_approved_on="2026-11-03",
        actual_run="offline_preview",
        transaction_test="memory_double_only",
        correction_rows=165,
        guard_rows=233,
        human_references_preserved=200,
        untouched_rows=77533,
        simulated_apply_matches_frozen_candidate=True,
        simulated_retry_did_not_reapply=True,
        simulated_rollback_restores_original_values=True,
        legacy_gate=preview["legacy_gate"],
        anchors_block_human_flow=False,
        min_l1_jaccard=0.7,
        real_applied=False,
        real_receipt_exists=False,
        database_reads=0,
        database_writes=0,
        model_calls=0,
        schema_sql_executed=False,
        protected_files_unchanged=len(protected),
        byte_identical_preview_files=len(names),
        postgres_server_integration_tested=False,
        caveat="Transaction double and mocked psycopg boundary only. No live locks, permissions, schema, commit or xmin behavior verified against a server.",
    )
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "protected-inputs.json").write_text(json.dumps(protected, indent=2) + "\n")
    manifest = dict(
        inputs={str(p): _sha256(p) for p in (policy, approval)},
        implementation={
            str(Path(__file__).resolve()): _sha256(Path(__file__)),
            str(here.parents[2] / "tests/test_human_correction_flow.py"): _sha256(
                here.parents[2] / "tests/test_human_correction_flow.py"
            ),
        },
        artifacts={
            str(p.relative_to(output)): _sha256(p) for p in output.rglob("*") if p.is_file()
        },
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.output.resolve())
