"""CSV boundary for nested, train-only regularized class corrections."""

import json

import pytest

from classificator.evaluation.d1_class_bias import evaluate_d1_class_bias
from tests.test_d1_temperature import fixture, read, write


def test_class_bias_corrects_wrong_ranking_using_training_folds_only(tmp_path):
    # Every fold has equal class counts; native p heavily overstates class1.
    source = fixture(tmp_path / "in", [0.8, 0.05, 0.05, 0.05, 0.05], [1, 2, 3, 4, 5])
    evaluate_d1_class_bias(source, source / "references.csv", tmp_path / "out")
    fits = json.loads((tmp_path / "out/fits.json").read_text())
    for model in fits.values():
        assert model["selected_lambda"] == 0.01
        b = model["fit"]["bias"]
        assert sum(b) == pytest.approx(0, abs=1e-12)
        assert b[0] < 0 < b[1]
        assert b[1:] == pytest.approx([b[1]] * 4)
        assert model["fit"]["gradient_max"] <= 1e-9
    rows = read(tmp_path / "out/predictions.csv")
    assert {r["d1_native"] for r in rows[:15]} == {"1"}
    assert {r["d1_class_bias"] for r in rows[:15]} == {"3"}
    # Challenge p=(.4,.25,.2,.1,.05): class2 becomes modal, formerly class1.
    assert max(range(1, 6), key=lambda k: float(rows[-1][f"bias_p_L{k}"])) == 2
    assert set(fits["outer:0"]["fit"]["train_ids"]).isdisjoint({"1", "2", "3", "4", "5"})


def test_balanced_uniform_data_choose_identity_and_export_report_and_provenance(tmp_path):
    source = fixture(tmp_path / "in", [0.2] * 5, [1, 2, 3, 4, 5])
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    report = evaluate_d1_class_bias(source, source / "references.csv", tmp_path / "out")
    fits = json.loads((tmp_path / "out/fits.json").read_text())
    assert all(m["selected_lambda"] is None and m["fit"]["bias"] == [0] * 5 for m in fits.values())
    assert report["cohorts"]["150"]["d1_class_bias"]["all"]["severe"] == 6
    assert report["paired"]["150"]["d1_native"]["all"] == dict(
        severe_avoided=0, severe_introduced=0
    )
    assert report["automatic_promotion"] is False
    assert report["probability_metrics"]["150"]["class_bias"]["nll"] == pytest.approx(
        1.6094379124341003
    )
    assert report["decisions"]["baseline_gate"]["no_regression_checks"]["50:true5:severe"] is None
    protocol = json.loads((tmp_path / "out/protocol.json").read_text())
    assert protocol["lambdas_strongest_first"] == [None, 10, 1, 0.1, 0.01]
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before


def test_ledger_contains_analytic_regularized_solution_and_disjoint_inner_splits(tmp_path):
    import math

    # For all labels5, p ∝ (.1e,.1e,.1e,.1e,.6e^-4), lambda=.1:
    # q=(.1,.1,.1,.1,.6), b=(-1,-1,-1,-1,4); data gradient + lambda*b = 0.
    weights = [0.1 * math.e] * 4 + [0.6 * math.exp(-4)]
    source = fixture(tmp_path / "in", [v / sum(weights) for v in weights], [5, 5])
    evaluate_d1_class_bias(source, source / "references.csv", tmp_path / "out")
    fits = json.loads((tmp_path / "out/fits.json").read_text())
    for name, model in fits.items():
        for candidate in model["candidates"]:
            for split in candidate["splits"].values():
                assert set(split["fit"]["train_ids"]).isdisjoint(split["validation_ids"])
                assert set(split["fit"]["train_ids"]) | set(split["validation_ids"]) == set(
                    model["fit"]["train_ids"]
                )
                if candidate["lambda_"] == 0.1:
                    assert split["fit"]["bias"] == pytest.approx([-1, -1, -1, -1, 4], abs=1e-7)
    assert {r["d1_class_bias"] for r in read(tmp_path / "out/predictions.csv")[:6]} == {"5"}


def test_outer_and_challenge_labels_never_leak_into_fits_or_lambda_selection(tmp_path):
    source = fixture(tmp_path / "in")
    evaluate_d1_class_bias(source, source / "references.csv", tmp_path / "original")
    original = read(source / "references.csv")
    before = json.loads((tmp_path / "original/fits.json").read_text())

    def predictions(folder, ids):
        return {
            r["word_id"]: {k: v for k, v in r.items() if k not in {"human_level", "bias_nll"}}
            for r in read(folder / "predictions.csv")
            if r["word_id"] in ids
        }

    holdout = {str(i) for i in range(1, 9)}
    write(
        source / "references.csv",
        [dict(r, human_level=5) if r["word_id"] in holdout else r for r in original],
    )
    evaluate_d1_class_bias(source, source / "references.csv", tmp_path / "changed-fold")
    after = json.loads((tmp_path / "changed-fold/fits.json").read_text())
    assert before["outer:0"] == after["outer:0"]
    assert before["outer:1"] != after["outer:1"]
    assert predictions(tmp_path / "original", holdout) == predictions(
        tmp_path / "changed-fold", holdout
    )
    # Inner fit in outer1/inner0 excludes modified fold0 as well.
    for old, new in zip(before["outer:1"]["candidates"], after["outer:1"]["candidates"]):
        assert old["splits"]["0"]["fit"] == new["splits"]["0"]["fit"]
    write(
        source / "references.csv",
        [dict(r, human_level=5) if r["word_id"] in {"25", "26"} else r for r in original],
    )
    evaluate_d1_class_bias(source, source / "references.csv", tmp_path / "changed-50")
    assert json.loads((tmp_path / "changed-50/fits.json").read_text()) == before
    all_ids = {r["word_id"] for r in original}
    assert predictions(tmp_path / "original", all_ids) == predictions(
        tmp_path / "changed-50", all_ids
    )


@pytest.mark.parametrize("defect", ["two_folds", "nan", "identity", "family", "hash"])
def test_invalid_inputs_never_publish_partial_output(tmp_path, defect):
    import hashlib

    source = fixture(tmp_path / "in")
    rows = read(source / "features.csv")
    manifest = json.loads((source / "inputs.json").read_text())
    if defect == "two_folds":
        for r in rows:
            if r["fold"] == "2":
                r["fold"] = "1"
        manifest["folds"] = ["0", "1"]
    if defect == "nan":
        rows[0]["p_L1"] = "nan"
    if defect == "identity":
        rows[0]["word"] = "badidentity"
    if defect == "family":
        rows[8]["group"] = rows[0]["group"]
    if defect == "hash":
        rows[0]["wordfreq"] = ".1"
    write(source / "features.csv", rows)
    if defect != "hash":
        manifest["features_sha256"] = hashlib.sha256(
            (source / "features.csv").read_bytes()
        ).hexdigest()
    (source / "inputs.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        evaluate_d1_class_bias(source, source / "references.csv", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_zero_probabilities_missing_classes_and_artifact_integrity(tmp_path):
    import hashlib
    import math

    source = fixture(tmp_path / "in", [1, 0, 0, 0, 0], [5, 5])
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    evaluate_d1_class_bias(source, source / "references.csv", tmp_path / "out")
    for row in read(tmp_path / "out/predictions.csv"):
        p = [float(row[f"bias_p_L{k}"]) for k in range(1, 6)]
        assert all(math.isfinite(v) and 0 < v <= 1 for v in p)
        assert sum(p) == pytest.approx(1)
    manifest = json.loads((tmp_path / "out/manifest.json").read_text())
    for name, digest in manifest["artifacts"].items():
        assert hashlib.sha256((tmp_path / "out" / name).read_bytes()).hexdigest() == digest
    old = (tmp_path / "out/predictions.csv").read_bytes()
    with pytest.raises(FileExistsError):
        evaluate_d1_class_bias(source, source / "references.csv", tmp_path / "out")
    assert (tmp_path / "out/predictions.csv").read_bytes() == old
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
