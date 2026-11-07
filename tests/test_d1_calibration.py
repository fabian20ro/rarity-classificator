"""CSV evaluation boundary: training isolation, monotonicity and complete cohorts."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from classificator.evaluation.d1_calibration import evaluate_d1_calibration


def write(path, rows):
    with path.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def fixture(root):
    root.mkdir(exist_ok=True)
    features, labels = [], []
    for i, (cohort, fold, x, y) in enumerate(
        [
            ("150", 0, 2, 1),
            ("150", 0, 3, 5),
            ("150", 1, 2, 1),
            ("150", 1, 3, 5),
            ("150", 2, 2, 1),
            ("150", 2, 3, 5),
            ("50", "", 2.375, 2),
            ("50", "", 2.75, 4),
        ],
        1,
    ):
        word = "form" + chr(96 + i)
        features.append(
            dict(
                word_id=str(i),
                word=word,
                cohort=cohort,
                group="g" + str(i),
                fold=str(fold),
                wordfreq="",
                historical_baseline="4",
                p_L1=0,
                p_L2=3 - x,
                p_L3=x - 2,
                p_L4=0,
                p_L5=0,
            )
        )
        labels.append(dict(word_id=str(i), word=word, human_level=y))
    write(root / "features.csv", features)
    write(root / "references.csv", labels)
    seal(root)
    return root


def seal(root):
    features = read(root / "features.csv")
    manifest = dict(
        schema=1,
        policy="d1-monotone-affine-v3",
        arm="A",
        cohort_sizes={c: sum(r["cohort"] == c for r in features) for c in ["150", "50"]},
        folds=sorted({r["fold"] for r in features if r["cohort"] == "150"}),
        features_sha256=hashlib.sha256((root / "features.csv").read_bytes()).hexdigest(),
    )
    (root / "inputs.json").write_text(json.dumps(manifest))


def test_fold_calibration_recovers_affine_scale_and_lower_half_tie(tmp_path):
    source = fixture(tmp_path / "in")
    evaluate_d1_calibration(source, source / "references.csv", tmp_path / "out")
    rows = read(tmp_path / "out/predictions.csv")
    assert [int(r["d1_calibrated"]) for r in rows] == [1, 5, 1, 5, 1, 5, 2, 4]
    report = json.loads((tmp_path / "out/report.json").read_text())
    assert report["cohorts"]["150"]["d1_calibrated"]["all"]["severe"] == 0
    assert report["cohorts"]["150"]["baseline"]["all"]["severe"] == 3
    fits = json.loads((tmp_path / "out/fits.json").read_text())
    assert set(fits["outer:0"]["train_ids"]).isdisjoint({"1", "2"})
    assert fits["full150"]["train_ids"] == ["1", "2", "3", "4", "5", "6"]


def test_combination_adds_d1_information_over_calibrated_baseline(tmp_path):
    source = fixture(tmp_path / "in")
    evaluate_d1_calibration(source, source / "references.csv", tmp_path / "out")
    rows = read(tmp_path / "out/predictions.csv")
    assert [int(r["combined"]) for r in rows] == [1, 5, 1, 5, 1, 5, 2, 4]
    assert {r["baseline_calibrated"] for r in rows} == {"3"}
    fits = json.loads((tmp_path / "out/fits.json").read_text())
    assert fits["full150"]["models"]["combined"]["coefficients"]["baseline"] == 0


def test_split_family_is_rejected_before_any_output(tmp_path):
    source = fixture(tmp_path / "in")
    rows = read(source / "features.csv")
    rows[2]["group"] = rows[0]["group"]
    write(source / "features.csv", rows)
    seal(source)
    with pytest.raises(ValueError, match="group"):
        evaluate_d1_calibration(source, source / "references.csv", tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "defect",
    [
        "probability",
        "normalization",
        "label",
        "frequency",
        "label_column",
        "fold",
        "size",
        "orthographic_family",
    ],
)
def test_invalid_frozen_inputs_fail_closed(tmp_path, defect):
    source = fixture(tmp_path / "in")
    rows = read(source / "features.csv")
    if defect == "probability":
        rows[0]["p_L1"] = "nan"
    if defect == "normalization":
        rows[0]["p_L1"] = "0.3"
    if defect == "frequency":
        rows[0]["wordfreq"] = "-1"
    if defect == "fold":
        rows[0]["fold"] = ""
    if defect == "label_column":
        for row in rows:
            row["human_level"] = "5"
    if defect == "orthographic_family":
        rows[0]["word"] = "ata"
        rows[2]["word"] = "ată"
        refs = read(source / "references.csv")
        refs[0]["word"] = "ata"
        refs[2]["word"] = "ată"
        write(source / "references.csv", refs)
    write(source / "features.csv", rows)
    seal(source)
    if defect == "label":
        refs = read(source / "references.csv")
        refs[0]["human_level"] = "6"
        write(source / "references.csv", refs)
    if defect == "size":
        m = json.loads((source / "inputs.json").read_text())
        m["cohort_sizes"]["150"] += 1
        (source / "inputs.json").write_text(json.dumps(m))
    with pytest.raises(ValueError):
        evaluate_d1_calibration(source, source / "references.csv", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_holdout_labels_never_change_own_fold_fit_and_50_never_change_any_prediction(tmp_path):
    source = fixture(tmp_path / "in")
    features = read(source / "features.csv")
    for r in features:
        r["wordfreq"] = "0.001" if float(r["p_L2"]) == 1 else "0.00001"
    write(source / "features.csv", features)
    seal(source)
    evaluate_d1_calibration(source, source / "references.csv", tmp_path / "original")
    original = read(source / "references.csv")
    changed = [dict(r, human_level=3) if r["word_id"] in {"1", "2"} else r for r in original]
    write(source / "references.csv", changed)
    evaluate_d1_calibration(source, source / "references.csv", tmp_path / "changed-fold")
    old = json.loads((tmp_path / "original/fits.json").read_text())
    new = json.loads((tmp_path / "changed-fold/fits.json").read_text())
    assert old["outer:0"] == new["outer:0"]

    def predictions(folder, ids=None):
        return {
            r["word_id"]: {k: v for k, v in r.items() if k != "human_level"}
            for r in read(folder / "predictions.csv")
            if ids is None or r["word_id"] in ids
        }

    assert predictions(tmp_path / "original", {"1", "2"}) == predictions(
        tmp_path / "changed-fold", {"1", "2"}
    )
    write(
        source / "references.csv",
        [dict(r, human_level=5) if r["word_id"] in {"7", "8"} else r for r in original],
    )
    evaluate_d1_calibration(source, source / "references.csv", tmp_path / "changed-50")
    assert json.loads((tmp_path / "changed-50/fits.json").read_text()) == old
    assert predictions(tmp_path / "original") == predictions(tmp_path / "changed-50")


def test_combination_uses_two_independent_monotone_signals(tmp_path):
    source = fixture(tmp_path / "in")
    features = []
    labels = []
    for i in range(14):
        y = 1 + i % 4
        x = 2 + i % 2
        cohort = "150" if i < 12 else "50"
        features.append(
            dict(
                word_id=str(i + 1),
                word="form" + chr(97 + i),
                cohort=cohort,
                group="g" + str(i),
                fold=str(i // 4) if i < 12 else "",
                wordfreq=0.001 if y <= 2 else 0.00001,
                historical_baseline=4,
                p_L1=0,
                p_L2=3 - x,
                p_L3=x - 2,
                p_L4=0,
                p_L5=0,
            )
        )
        labels.append(dict(word_id=str(i + 1), word="form" + chr(97 + i), human_level=y))
    write(source / "features.csv", features)
    write(source / "references.csv", labels)
    seal(source)
    evaluate_d1_calibration(source, source / "references.csv", tmp_path / "out")
    rows = read(tmp_path / "out/predictions.csv")
    assert [int(r["combined"]) for r in rows] == [1, 2, 3, 4] * 3 + [1, 2]
    fits = json.loads((tmp_path / "out/fits.json").read_text())
    assert all(v > 0 for v in fits["full150"]["models"]["combined"]["coefficients"].values())


def test_negative_signal_is_not_inverted_and_collinear_signals_are_stable(tmp_path):
    source = fixture(tmp_path / "in")
    refs = read(source / "references.csv")
    write(source / "references.csv", [dict(r, human_level=6 - int(r["human_level"])) for r in refs])
    evaluate_d1_calibration(source, source / "references.csv", tmp_path / "negative")
    assert {r["d1_calibrated"] for r in read(tmp_path / "negative/predictions.csv")} == {"3"}
    write(source / "references.csv", refs)
    features = read(source / "features.csv")
    for r in features:
        r["wordfreq"] = ".001" if float(r["p_L2"]) == 1 else ".00001"
    write(source / "features.csv", features)
    seal(source)
    evaluate_d1_calibration(source, source / "references.csv", tmp_path / "collinear")
    assert [int(r["combined"]) for r in read(tmp_path / "collinear/predictions.csv")][:6] == [
        1,
        5,
    ] * 3


def test_decision_requires_gain_over_baseline_and_separate_baseline_calibration(tmp_path):
    source = fixture(tmp_path / "in")
    report = evaluate_d1_calibration(source, source / "references.csv", tmp_path / "out")
    assert report["decisions"]["combined"]["passes_vs_baseline"] is True
    assert report["decisions"]["combined"]["adds_value_vs_baseline_calibrated"] is True
    assert report["automatic_promotion"] is False
    assert report["paired"]["150"]["combined"]["all"]["severe_avoided"] == 3
    assert report["paired"]["150"]["combined"]["all"]["severe_introduced"] == 0
