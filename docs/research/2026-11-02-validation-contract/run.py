"""Pin existing data, run the audit-only contract, reconcile it, prove upload still blocks."""

import argparse
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from classificator.evaluation.dataset import _sha256
from classificator.evaluation.validation_contract import audit_validation_contract, SCHEMA
from classificator.models import UploadMode
from classificator.run_csv_repository import RunCsvRepository
from classificator.steps.step4_upload import Step4Options, run_step4


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class ForbiddenBoundary:
    def __getattr__(self, name):
        raise AssertionError(f"Upload/DB boundary reached: {name}")


def run(base, out):
    out.mkdir(parents=True, exist_ok=False)
    code = Path(__file__).resolve().parents[3]
    previous = base / "l1-audit-2026-11-02"
    conservative = base / "conservative-export-2026-11-01"
    protected = json.loads((previous / "protected-inputs.json").read_text())
    protected.update({str(p): _sha256(p) for p in previous.rglob("*") if p.is_file()})
    for relative in (
        "src/classificator/steps/step4_upload.py",
        "src/classificator/tools/quality_audit.py",
        "docs/rarity-anchor-l1-ro.txt",
    ):
        p = code / relative
        protected[str(p)] = _sha256(p)
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    inventory = base.parent / "rarity/step1_words.csv"

    def source(sid, role, unit, path, date, provenance, **extra):
        return dict(
            id=sid,
            role=role,
            unit=unit,
            path=str(path),
            sha256=_sha256(path),
            universe_sha256=_sha256(inventory),
            recorded_on=date,
            provenance=provenance,
            **extra,
        )

    human_catalog = {
        r["source_id"]: Path(r["path"]) for r in read(conservative / "reference-sources.csv")
    }
    contract = dict(
        schema=SCHEMA,
        mode="audit",
        as_of="2026-11-02",
        inventory=dict(path=str(inventory), sha256=_sha256(inventory)),
        legacy_thresholds=dict(l1_jaccard=0.7, anchor_precision=0.8, anchor_recall=0.8),
        references=[
            source(
                "history",
                "historical_snapshot",
                "inventory_id",
                base.parent / "rarity/reference/current_db_levels.csv",
                "2026-02-15",
                "Project journal documents snapshot before later February uploads; historical only, no live DB verification",
                level_column="rarity_level",
            ),
            source(
                "seed",
                "positive_seed",
                "exact_form",
                code / "docs/rarity-anchor-l1-ro.txt",
                None,
                "Repository positive seed, incomplete; provenance does not attest annotation date or human validation",
            ),
            source(
                "human_pilot150",
                "human_labels",
                "exact_form",
                human_catalog["human_pilot150"],
                "2026-10-21",
                "Canonical final working150; mixed provenance,113 initial opaque and37 clarified references, no new labels",
                level_column="working_level",
                selection="development",
            ),
            source(
                "human_review50",
                "human_labels",
                "exact_form",
                human_catalog["human_review50"],
                "2026-10-31",
                "Imported completed Sites50; selected by risk, preserve original user ratings",
                level_column="working_level",
                selection="risk_selected",
            ),
        ],
        candidates=[
            source(
                "baseline",
                "candidate",
                "exact_form",
                base / "offline-wordfreq-2026-10-24/export/scores.csv",
                "2026-10-24",
                "Frozen full fitted wordfreq+fallback export; not OOF; original manifest retained",
                level_column="rarity_level",
                label_use=dict(human_pilot150="fit", human_review50="none"),
            ),
            source(
                "conservative",
                "candidate",
                "exact_form",
                conservative / "export/candidate.csv",
                "2026-11-01",
                "Frozen human exact-form overlay; agreement on reviewed forms is by construction",
                level_column="final_level",
                label_use=dict(human_pilot150="override", human_review50="override"),
            ),
        ],
    )
    contract_path = out / "contract.json"
    contract_path.write_text(json.dumps(contract, indent=2) + "\n")
    (out / "protected-inputs.json").write_text(json.dumps(protected, indent=2) + "\n")
    with (
        patch("subprocess.run", side_effect=AssertionError("Processes forbidden")),
        patch("subprocess.Popen", side_effect=AssertionError("Processes forbidden")),
        patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
        patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
    ):
        report = audit_validation_contract(contract_path, out / "audit")
        with TemporaryDirectory(dir=out) as tmp:
            replay = Path(tmp) / "audit"
            assert audit_validation_contract(contract_path, replay) == report
            assert {p.name for p in replay.iterdir()} == {p.name for p in (out / "audit").iterdir()}
            for p in replay.iterdir():
                assert p.read_bytes() == (out / "audit" / p.name).read_bytes(), p.name
        # Real upload entrypoint and real gate, with only external-effect boundaries forbidden.
        blocked = {}
        for candidate in contract["candidates"]:
            options = Step4Options(
                final_csv_path=Path(candidate["path"]),
                mode=UploadMode.PARTIAL,
                report_path=out / (candidate["id"] + "-should-not-exist.csv"),
                upload_batch_id=None,
                reference_csv=Path(contract["references"][0]["path"]),
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
                blocked[candidate["id"]] = str(error)
            else:
                raise AssertionError("Upload unexpectedly passed")
            assert not options.report_path.exists()
    prior = json.loads((previous / "report.json").read_text())
    assert report["inventory_rows"] == 77698 and report["exact_forms"] == 75147
    assert report["human_forms"] == 200 and report["unknown_forms"] == 74947
    assert report["status"] == "audit_only" and report["upload_authorized"] is False
    for cid, previous_name in (("baseline", "baseline"), ("conservative", "candidate")):
        current = report["candidates"][cid]
        earlier = prior["methods"][previous_name]
        drift, seed = current["historical"]["history"], current["seeds"]["seed"]
        assert drift["jaccard"] == earlier["quality"]["l1_jaccard"]
        assert drift["maximum_jaccard"] == earlier["maximum_jaccard_at_fixed_counts"]
        assert seed["recall"] == earlier["quality"]["anchor_recall"]
        assert seed["membership_ratio"] == earlier["quality"]["anchor_precision"]
        assert seed["semantic_precision"] is None
        for sid, human in current["humans"].items():
            col = "baseline_level" if cid == "baseline" else "candidate_level"
            earlier_human = prior["human_comparison"][sid][col]
            metrics = human["metrics"]
            assert metrics["n"] == earlier_human["all"]["n"]
            assert metrics["severe"] == earlier_human["all"]["severe"]
            assert metrics["excess_error_total"] == earlier_human["all"]["excess"]
            for level in ("4", "5"):
                assert metrics["per_level"][level]["support"] == earlier_human["human" + level]["n"]
                assert (
                    metrics["per_level"][level]["severe"]
                    == earlier_human["human" + level]["severe"]
                )
    # Independently reconcile exported comparisons and denominators, using original reference rows.
    comparison = read(out / "audit/human-comparison.csv")
    assert len(comparison) == 400
    for spec in contract["references"]:
        if spec["role"] != "human_labels":
            continue
        labels = {r["word"].casefold(): int(r["working_level"]) for r in read(Path(spec["path"]))}
        for cid in ("baseline", "conservative"):
            rows = [r for r in comparison if r["candidate"] == cid and r["source"] == spec["id"]]
            assert {r["word"]: int(r["human_level"]) for r in rows} == labels
            human = report["candidates"][cid]["humans"][spec["id"]]
            predicted = [r for r in rows if r["candidate_level"] == "1"]
            correct = [r for r in predicted if r["human_level"] == "1"]
            true_l1 = sum(n == 1 for n in labels.values())
            assert human["labelled_predicted_l1"] == len(predicted)
            assert human["labelled_true_l1"] == true_l1
            assert human["l1_precision_on_labelled_forms"] == (
                len(correct) / len(predicted) if predicted else None
            )
            assert human["l1_recall_on_labelled_forms"] == (
                len(correct) / true_l1 if true_l1 else None
            )
            if cid == "conservative":
                assert all(r["candidate_level"] == r["human_level"] for r in rows)
                assert (
                    human["override_preserved"]
                    and human["interpretation"] == "integrity_only_not_accuracy"
                )
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    result = dict(
        protected_files_unchanged=len(protected),
        replay_byte_identical_artifacts=7,
        prior_independent_metrics="PASS",
        human_comparisons_reconciled=400,
        human_overrides_preserved=200,
        upload_entrypoint_blocked=blocked,
        external_effect_boundaries_reached=False,
        model_calls=0,
        database_writes=0,
        implementation_sha256=_sha256(code / "src/classificator/evaluation/validation_contract.py"),
        runner_sha256=_sha256(Path(__file__).resolve()),
        contract_sha256=_sha256(contract_path),
    )
    (out / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.base.resolve(), args.output.resolve())
