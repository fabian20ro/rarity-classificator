"""Replay an already captured single-SELECT snapshot; no network or database access."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from classificator.evaluation.dataset import _lexeme, _sha256, _write_csv
from classificator.evaluation.form_evidence_audit import _check_export
from classificator.evaluation.migration_dry_run import plan_migration
from classificator.evaluation.validation_contract import audit_validation_contract
from classificator.models import UploadMode
from classificator.run_csv_repository import RunCsvRepository
from classificator.steps.step4_upload import Step4Options, run_step4


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class ForbiddenBoundary:
    def __getattr__(self, name):
        raise AssertionError(f"External effect reached: {name}")


def run(base, snapshot, out):
    out.mkdir(parents=True, exist_ok=False)
    code = Path(__file__).resolve().parents[3]
    previous = base / "validation-contract-2026-11-02"
    conservative = base / "conservative-export-2026-11-01/export"
    _check_export(conservative, {"candidate.csv", "references.csv"})
    protected = json.loads((previous / "protected-inputs.json").read_text())
    protected.update({str(p): _sha256(p) for p in previous.rglob("*") if p.is_file()})
    protected[str(snapshot)] = _sha256(snapshot)
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    (out / "protected-inputs.json").write_text(json.dumps(protected, indent=2) + "\n")
    raw = json.loads(snapshot.read_text())
    assert raw["project_id"] == "pdliedweugywbiczajxn"
    assert raw["row_count"] == len(raw["rows"]) == 77698
    assert (
        raw["query"]
        == "SELECT statement_timestamp() AS captured_at, current_database() AS database_name, current_setting('server_version') AS server_version, count(*) AS row_count, json_agg(json_build_array(id,word,type,rarity_level) ORDER BY id) AS rows FROM public.words"
    )
    assert all(
        len(r) == 4
        and isinstance(r[0], int)
        and isinstance(r[1], str)
        and isinstance(r[2], str)
        and type(r[3]) is int
        and 1 <= r[3] <= 5
        for r in raw["rows"]
    )
    assert len({r[0] for r in raw["rows"]}) == len(raw["rows"])
    live = [dict(word_id=i, word=w, type=p, rarity_level=n) for i, w, p, n in raw["rows"]]
    _write_csv(out / "live-snapshot.csv", ["word_id", "word", "type", "rarity_level"], live)
    _write_csv(
        out / "live-inventory.csv",
        ["word_id", "word", "type"],
        [{k: r[k] for k in ("word_id", "word", "type")} for r in live],
    )
    metadata = {k: v for k, v in raw.items() if k != "rows"}
    metadata.update(
        raw_sha256=_sha256(snapshot),
        csv_sha256=_sha256(out / "live-snapshot.csv"),
        scope="public.words four columns, single SELECT; transaction read-only setting not asserted; no DML/DDL",
    )
    (out / "snapshot-provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
    with (
        patch("subprocess.run", side_effect=AssertionError("Processes forbidden")),
        patch("subprocess.Popen", side_effect=AssertionError("Processes forbidden")),
        patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
        patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
    ):
        summary = plan_migration(
            conservative / "candidate.csv", out / "live-snapshot.csv", out / "plan"
        )
        assert summary["mapping_complete"] and summary["mapped_rows"] == 77698
        source = {r["word_id"]: r for r in read(conservative / "candidate.csv")}
        actual = {str(r["word_id"]): r for r in live}
        planned = read(out / "plan/plan.csv")
        source_groups, live_groups = defaultdict(list), defaultdict(list)
        for i, r in source.items():
            source_groups[(_lexeme(r["word"]), r["type"])].append(i)
        for i, r in actual.items():
            live_groups[(_lexeme(r["word"]), r["type"])].append(i)
        assert source_groups.keys() == live_groups.keys()
        assert all(len(source_groups[k]) == len(live_groups[k]) for k in source_groups)
        assert len(planned) == len({r["live_word_id"] for r in planned}) == len(actual)
        unique_deltas = Counter()
        for p in planned:
            row = actual[p["live_word_id"]]
            key = (_lexeme(row["word"]), row["type"])
            old_ids = source_groups[key]
            assert sorted(json.loads(p["source_word_ids_json"])) == sorted(map(int, old_ids))
            assert len({source[i]["final_level"] for i in old_ids}) == 1
            assert all(p["proposed_level"] == source[i]["final_level"] for i in old_ids)
            assert p["word"] == row["word"] and p["type"] == row["type"]
            assert int(p["current_level"]) == row["rarity_level"]
            assert int(p["change"]) == int(p["proposed_level"]) - row["rarity_level"]
            assert int(p["absolute_gap"]) == abs(int(p["change"]))
            if len(old_ids) == 1:
                unique_deltas[str(int(p["live_word_id"]) - int(old_ids[0]))] += 1
        large = read(out / "plan/level-conflicts.csv")
        assert large == [r for r in planned if int(r["absolute_gap"]) >= 2]
        # Audit-only projection in the live ID universe, preserving every source score.
        projected = [
            dict(
                word_id=p["live_word_id"],
                word=p["word"],
                type=p["type"],
                final_level=p["proposed_level"],
            )
            for p in planned
        ]
        _write_csv(
            out / "audit-candidate-projection.csv",
            ["word_id", "word", "type", "final_level"],
            projected,
        )
        contract = json.loads((previous / "contract.json").read_text())
        contract["as_of"] = raw["captured_at"][:10]
        inventory = out / "live-inventory.csv"
        contract["inventory"] = dict(path=str(inventory), sha256=_sha256(inventory))
        human_count = 0
        for ref in contract["references"]:
            original_path = ref["path"]
            original_hash = ref["sha256"]
            if ref["role"] == "historical_snapshot":
                path = out / "live-snapshot.csv"
                ref["recorded_on"] = raw["captured_at"][:10]
                ref["provenance"] = (
                    "Fresh single-SELECT operational snapshot, not human truth; see snapshot-provenance.json"
                )
            elif ref["role"] == "human_labels":
                path = out / (ref["id"] + "-live-projection.csv")
                mapped = []
                for r in read(Path(original_path)):
                    original = source[r["word_id"]]
                    assert _lexeme(original["word"]) == _lexeme(r["word"])
                    key = (_lexeme(r["word"]), original["type"])
                    live_ids = sorted(live_groups[key], key=int)
                    mapped.append(
                        dict(
                            r,
                            word_id=live_ids[0],
                            original_word_id=r["word_id"],
                            live_equivalent_ids_json=json.dumps(list(map(int, live_ids))),
                        )
                    )
                    human_count += 1
                _write_csv(path, list(mapped[0]), mapped)
                ref["provenance"] += (
                    f"; exact-form/POS projection from {original_path} sha256={original_hash}; representative ID is not a claimed duplicate-row identity"
                )
            else:
                path = Path(original_path)
            ref.update(path=str(path), sha256=_sha256(path), universe_sha256=_sha256(inventory))
        assert human_count == 200
        contract["candidates"] = [c for c in contract["candidates"] if c["id"] == "conservative"]
        spec = contract["candidates"][0]
        spec.update(
            path=str(out / "audit-candidate-projection.csv"),
            sha256=_sha256(out / "audit-candidate-projection.csv"),
            universe_sha256=_sha256(inventory),
            provenance=spec["provenance"] + "; live-ID audit-only projection, no upload",
        )
        contract_path = out / "contract.json"
        contract_path.write_text(json.dumps(contract, indent=2) + "\n")
        audit = audit_validation_contract(contract_path, out / "validation")
        assert audit["upload_authorized"] is False
        for h in audit["candidates"]["conservative"]["humans"].values():
            assert h["override_preserved"] and h["metrics"]["severe"] == 0
        with TemporaryDirectory(dir=out) as tmp:
            replay = Path(tmp)
            plan_migration(
                conservative / "candidate.csv", out / "live-snapshot.csv", replay / "plan"
            )
            audit_validation_contract(contract_path, replay / "validation")
            for name in ("plan", "validation"):
                assert {p.name for p in (out / name).iterdir()} == {
                    p.name for p in (replay / name).iterdir()
                }
                for p in (replay / name).iterdir():
                    assert p.read_bytes() == (out / name / p.name).read_bytes(), p.name
        options = Step4Options(
            final_csv_path=out / "audit-candidate-projection.csv",
            mode=UploadMode.PARTIAL,
            report_path=out / "must-not-exist.csv",
            upload_batch_id=None,
            reference_csv=out / "live-snapshot.csv",
            anchor_l1_file=Path(contract["references"][1]["path"]),
        )
        try:
            run_step4(
                options,
                word_store=ForbiddenBoundary(),
                repo=RunCsvRepository(),
                marker_writer=ForbiddenBoundary(),
            )
        except RuntimeError as error:
            assert str(error).startswith("Quality audit failed:"), str(error)
            gate_failure = str(error)
        else:
            raise AssertionError("Unexpected upload pass")
        assert not options.report_path.exists()
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    human_plan = [p for p in planned if p["decision_source"] == "human"]
    report = dict(
        snapshot=metadata,
        summary=summary,
        observed_unique_pair_id_deltas=dict(unique_deltas),
        duplicate_groups=sum(len(v) > 1 for v in source_groups.values()),
        human_rows=len(human_plan),
        human_changed_rows=sum(int(p["change"]) != 0 for p in human_plan),
        human_large_difference_rows=sum(int(p["absolute_gap"]) >= 2 for p in human_plan),
        validation=audit,
        upload_blocked=gate_failure,
        protected_files_unchanged=len(protected),
        replay_byte_identical_artifacts=13,
        original_human_references_preserved=human_count,
        model_calls=0,
        database_writes=0,
        caveats=[
            "Snapshot is operational state, not ground truth; differences are not automatically errors",
            "Duplicate groups have equivalent proposed scores, not proven per-row identity",
            "Observed ID delta is diagnostic only, never a mapping rule",
            "No executable update script or upload authorization",
        ],
    )
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    receipt = dict(
        inputs={str(snapshot): _sha256(snapshot)},
        implementation={str(Path(__file__).resolve()): _sha256(Path(__file__))},
        artifacts={str(p.relative_to(out)): _sha256(p) for p in out.rglob("*") if p.is_file()},
    )
    (out / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ("validation", "snapshot", "caveats")},
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.base.resolve(), args.snapshot.resolve(), args.output.resolve())
