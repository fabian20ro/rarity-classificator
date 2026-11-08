"""Temperature calibration through the agreed CSV evaluation interface."""

import csv
import hashlib
import json

import pytest

from classificator.evaluation.d1_temperature import evaluate_d1_temperature


def write(path, rows):
    with path.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def fixture(root, probabilities=None, labels=None):
    root.mkdir()
    probabilities = probabilities or [1 / 6, 1 / 6, 1 / 3, 1 / 6, 1 / 6]
    labels = labels or [1, 2, 3, 3, 3, 3, 4, 5]
    features, refs = [], []
    for i in range(3 * len(labels) + 2):
        pilot = i < 3 * len(labels)
        word = "form" + chr(97 + i // 26) + chr(97 + i % 26)
        p = probabilities if pilot else [0.4, 0.25, 0.2, 0.1, 0.05]
        features.append(
            dict(
                word_id=str(i + 1),
                word=word,
                cohort="150" if pilot else "50",
                group=f"g{i}",
                fold=str(i // len(labels)) if pilot else "",
                wordfreq="",
                historical_baseline=4,
                **{f"p_L{k}": v for k, v in enumerate(p, 1)},
            )
        )
        refs.append(dict(word_id=str(i + 1), word=word, human_level=labels[i % len(labels)]))
    write(root / "features.csv", features)
    write(root / "references.csv", refs)
    (root / "inputs.json").write_text(
        json.dumps(
            dict(
                schema=1,
                policy="d1-monotone-affine-v3",
                arm="A",
                cohort_sizes={"150": 3 * len(labels), "50": 2},
                folds=["0", "1", "2"],
                features_sha256=hashlib.sha256((root / "features.csv").read_bytes()).hexdigest(),
            )
        )
    )
    return root


def test_recovers_known_temperature_and_exports_full_distributions(tmp_path):
    # Empirical train proportions (1,1,4,1,1)/8 are exactly p**2 normalized.
    source = fixture(tmp_path / "in")
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    evaluate_d1_temperature(source, source / "references.csv", tmp_path / "out")
    fits = json.loads((tmp_path / "out/fits.json").read_text())
    for fit in fits.values():
        assert fit["temperature"] == pytest.approx(0.5, abs=1e-9)
        assert fit["location"] == "interior"
        assert fit["training_nll"] < fit["native_training_nll"]
    rows = read(tmp_path / "out/predictions.csv")
    assert len(rows) == 26
    assert rows[-1]["d1_native"] == "2"
    assert rows[-1]["d1_temperature"] == "1"
    assert [float(rows[-1][f"q_L{k}"]) for k in range(1, 6)] == pytest.approx(
        [64 / 110, 25 / 110, 16 / 110, 4 / 110, 1 / 110]
    )
    assert set(fits["outer:0"]["train_ids"]).isdisjoint(str(i) for i in range(1, 9))
    assert fits["full150"]["train_ids"] == [str(i) for i in range(1, 25)]
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    report = json.loads((tmp_path / "out/report.json").read_text())
    assert report["paired"]["150"]["baseline"]["all"] == dict(severe_avoided=3, severe_introduced=3)
    assert report["paired"]["150"]["d1_native"]["all"] == dict(
        severe_avoided=0, severe_introduced=0
    )
    assert report["cohorts"]["150"]["d1_temperature"]["true5"]["severe"] == 3
    assert report["decisions"]["baseline_gate"]["passes"] is False


def test_uniform_training_uses_identity_and_reports_empty_class_as_unobserved(tmp_path):
    source = fixture(tmp_path / "in", [0.2] * 5, [3, 3])
    report = evaluate_d1_temperature(source, source / "references.csv", tmp_path / "out")
    fits = json.loads((tmp_path / "out/fits.json").read_text())
    assert all(f["temperature"] == 1 and f["location"] == "flat" for f in fits.values())
    assert report["decisions"]["baseline_gate"]["no_regression_checks"]["50:true1:severe"] is None
    assert report["automatic_promotion"] is False
    assert report["cohorts"]["150"]["d1_temperature"]["all"]["severe"] == 0
    assert report["probability_metrics"]["150"]["native"]["nll"] == pytest.approx(
        1.6094379124341003
    )
    assert report["probability_metrics"]["150"]["temperature"]["brier"] == pytest.approx(0.8)


@pytest.mark.parametrize(
    "p,labels,temperature,location",
    [
        ([0.8, 0.05, 0.05, 0.05, 0.05], [1, 1], 0.05, "upper_beta_bound"),
        ([0.8, 0.05, 0.05, 0.05, 0.05], [5, 5], 20, "lower_beta_bound"),
        ([1, 0, 0, 0, 0], [5, 5], 20, "lower_beta_bound"),
    ],
)
def test_boundary_optima_and_zero_probabilities_stay_finite(
    tmp_path, p, labels, temperature, location
):
    import math

    source = fixture(tmp_path / "in", p, labels)
    report = evaluate_d1_temperature(source, source / "references.csv", tmp_path / "out")
    fits = json.loads((tmp_path / "out/fits.json").read_text())
    assert all(f["temperature"] == temperature and f["location"] == location for f in fits.values())
    for row in read(tmp_path / "out/predictions.csv"):
        probabilities = [float(row[f"q_L{k}"]) for k in range(1, 6)]
        assert sum(probabilities) == pytest.approx(1)
        assert all(math.isfinite(v) and 0 < v <= 1 for v in probabilities)
        assert int(row["d1_temperature"]) in range(1, 6)
    assert math.isfinite(report["probability_metrics"]["150"]["temperature"]["nll"])
    if 0 in p:
        assert fits["full150"]["floored_training_values"] == 24


def test_holdout_labels_cannot_affect_own_predictions_and_challenge_cannot_affect_any_fit(tmp_path):
    source = fixture(tmp_path / "in")
    evaluate_d1_temperature(source, source / "references.csv", tmp_path / "original")
    original = read(source / "references.csv")
    old_fits = json.loads((tmp_path / "original/fits.json").read_text())

    def predictions(folder, ids=None):
        return {
            r["word_id"]: {k: v for k, v in r.items() if k != "human_level"}
            for r in read(folder / "predictions.csv")
            if ids is None or r["word_id"] in ids
        }

    holdout = {str(i) for i in range(1, 9)}
    write(
        source / "references.csv",
        [dict(r, human_level=5) if r["word_id"] in holdout else r for r in original],
    )
    evaluate_d1_temperature(source, source / "references.csv", tmp_path / "changed-fold")
    new_fits = json.loads((tmp_path / "changed-fold/fits.json").read_text())
    assert new_fits["outer:0"] == old_fits["outer:0"]
    assert predictions(tmp_path / "original", holdout) == predictions(
        tmp_path / "changed-fold", holdout
    )
    write(
        source / "references.csv",
        [dict(r, human_level=5) if r["word_id"] in {"25", "26"} else r for r in original],
    )
    evaluate_d1_temperature(source, source / "references.csv", tmp_path / "changed-50")
    assert json.loads((tmp_path / "changed-50/fits.json").read_text()) == old_fits
    assert predictions(tmp_path / "original") == predictions(tmp_path / "changed-50")


@pytest.mark.parametrize(
    "defect", ["hash", "probability", "family", "identity", "labels_in_features"]
)
def test_invalid_input_publishes_no_partial_results(tmp_path, defect):
    source = fixture(tmp_path / "in")
    rows = read(source / "features.csv")
    if defect == "hash":
        rows[0]["wordfreq"] = ".1"
    elif defect == "probability":
        rows[0]["p_L1"] = "nan"
    elif defect == "family":
        rows[8]["group"] = rows[0]["group"]
    elif defect == "identity":
        rows[0]["word"] = "wrong"
    elif defect == "labels_in_features":
        rows = [dict(r, human_level=3) for r in rows]
    write(source / "features.csv", rows)
    if defect != "hash":
        manifest = json.loads((source / "inputs.json").read_text())
        manifest["features_sha256"] = hashlib.sha256(
            (source / "features.csv").read_bytes()
        ).hexdigest()
        (source / "inputs.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        evaluate_d1_temperature(source, source / "references.csv", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_artifacts_are_hashed_and_existing_output_never_overwritten(tmp_path):
    source = fixture(tmp_path / "in")
    evaluate_d1_temperature(source, source / "references.csv", tmp_path / "out")
    out = tmp_path / "out"
    before = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        evaluate_d1_temperature(source, source / "references.csv", out)
    assert {
        str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()
    } == before
    manifest = json.loads((out / "manifest.json").read_text())
    for name, digest in manifest["artifacts"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    protocol = json.loads((out / "protocol.json").read_text())
    assert {
        "d1_temperature.py",
        "d1_calibration.py",
        "frequency_calibration.py",
        "judge_comparison.py",
    } <= set(protocol["implementation"])
    assert (out / "comparators/predictions.csv").exists()
