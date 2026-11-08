"""Fixed ordinal decoding at the previously agreed CSV comparison boundary."""

import hashlib
import json

import pytest

from classificator.evaluation.d1_class_bias import evaluate_d1_class_bias
from classificator.evaluation.d1_ordinal import evaluate_d1_ordinal
from tests.test_d1_temperature import fixture, read, write


def source_pack(tmp_path, probabilities):
    inputs = fixture(tmp_path / "in", probabilities, [1, 2, 3, 4, 5])
    rows = read(inputs / "features.csv")
    for row in rows:
        row.update({f"p_L{k}": p for k, p in enumerate(probabilities, 1)})
    write(inputs / "features.csv", rows)
    manifest = json.loads((inputs / "inputs.json").read_text())
    manifest["features_sha256"] = hashlib.sha256((inputs / "features.csv").read_bytes()).hexdigest()
    (inputs / "inputs.json").write_text(json.dumps(manifest))
    evaluate_d1_class_bias(inputs, inputs / "references.csv", tmp_path / "saved")
    return inputs, tmp_path / "saved"


def test_expected_excess_cost_moves_median_to_lower_risk_action(tmp_path):
    inputs, saved = source_pack(tmp_path, [0.6, 0, 0, 0, 0.4])
    evaluate_d1_ordinal(inputs, inputs / "references.csv", saved, tmp_path / "out")
    rows = read(tmp_path / "out/predictions.csv")
    assert len(rows) == 17
    assert {r["d1_native"] for r in rows} == {"1"}
    assert {r["d1_ordinal"] for r in rows} == {"2"}
    for row in rows:
        assert [float(row[f"ordinal_risk_L{k}"]) for k in range(1, 6)] == pytest.approx(
            [1.2, 0.8, 1, 1.2, 1.8]
        )
        assert row["constant3"] == "3"


def test_report_distinguishes_severe_count_from_excess_and_constant3(tmp_path):
    inputs, saved = source_pack(tmp_path, [0.6, 0, 0, 0, 0.4])
    report = evaluate_d1_ordinal(inputs, inputs / "references.csv", saved, tmp_path / "out")
    values = report["cohorts"]["150"]
    assert values["d1_ordinal"]["all"]["severe"] == 6
    assert values["d1_ordinal"]["all"]["excess_error_total"] == 9
    assert values["constant3"]["all"]["severe"] == 6
    assert values["constant3"]["all"]["excess_error_total"] == 6
    assert values["d1_ordinal"]["true1"]["severe"] == 0
    assert values["d1_ordinal"]["true4"]["severe"] == 3
    assert values["d1_ordinal"]["true5"]["severe"] == 3
    assert report["paired"]["150"]["constant3"]["all"] == dict(
        severe_avoided=3, severe_introduced=3
    )
    assert report["decisions"]["constant3_gate"]["passes"] is False
    assert report["decisions"]["baseline_gate"]["no_regression_checks"]["50:true5:severe"] is None
    assert report["automatic_promotion"] is False
    assert report["fitted_parameters"] == 0
    assert not (tmp_path / "out/comparators").exists()
    assert (tmp_path / "out/protocol.json").exists()


@pytest.mark.parametrize(
    "p,expected",
    [
        ([0.5, 0, 0, 0, 0.5], 2),
        ([1, 0, 0, 0, 0], 1),
        ([0, 0, 0, 0, 1], 5),
        ([0, 0, 1, 0, 0], 3),
        ([0.2] * 5, 3),
    ],
)
def test_predeclared_tie_rule_preserves_median_when_optimal(tmp_path, p, expected):
    inputs, saved = source_pack(tmp_path, p)
    evaluate_d1_ordinal(inputs, inputs / "references.csv", saved, tmp_path / "out")
    assert {int(r["d1_ordinal"]) for r in read(tmp_path / "out/predictions.csv")} == {expected}


def test_all_reference_labels_and_unrelated_comparator_scores_cannot_change_decisions(tmp_path):
    inputs, saved = source_pack(tmp_path, [0.6, 0, 0, 0, 0.4])
    evaluate_d1_ordinal(inputs, inputs / "references.csv", saved, tmp_path / "before")
    refs = read(inputs / "references.csv")
    write(inputs / "references.csv", [dict(r, human_level=6 - int(r["human_level"])) for r in refs])
    evaluate_d1_class_bias(inputs, inputs / "references.csv", tmp_path / "changed-saved")
    evaluate_d1_ordinal(
        inputs, inputs / "references.csv", tmp_path / "changed-saved", tmp_path / "after"
    )

    def decisions(path):
        return [
            {
                k: v
                for k, v in r.items()
                if k == "word_id" or k == "d1_ordinal" or k.startswith("ordinal_risk_")
            }
            for r in read(path / "predictions.csv")
        ]

    assert decisions(tmp_path / "before") == decisions(tmp_path / "after")
    rows = read(tmp_path / "changed-saved/predictions.csv")
    for r in rows:
        for k in ["baseline", "d1_calibrated", "d1_temperature", "d1_class_bias"]:
            r[k] = "5"
    write(tmp_path / "changed-saved/predictions.csv", rows)
    seal_comparison(tmp_path / "changed-saved")
    evaluate_d1_ordinal(
        inputs, inputs / "references.csv", tmp_path / "changed-saved", tmp_path / "changed-controls"
    )
    assert decisions(tmp_path / "before") == decisions(tmp_path / "changed-controls")


def seal_comparison(saved):
    m = json.loads((saved / "manifest.json").read_text())
    m["artifacts"]["predictions.csv"] = hashlib.sha256(
        (saved / "predictions.csv").read_bytes()
    ).hexdigest()
    (saved / "manifest.json").write_text(json.dumps(m))


@pytest.mark.parametrize(
    "defect",
    [
        "csv_hash",
        "reference_hash",
        "missing",
        "duplicate",
        "identity",
        "partition",
        "probability",
        "level",
        "native",
        "constant3",
    ],
)
def test_inconsistent_frozen_comparisons_fail_without_output(tmp_path, defect):
    inputs, saved = source_pack(tmp_path, [0.6, 0, 0, 0, 0.4])
    rows = read(saved / "predictions.csv")
    if defect == "csv_hash":
        rows[0]["baseline"] = "5"
    if defect == "reference_hash":
        refs = read(inputs / "references.csv")
        refs[0]["human_level"] = "5"
        write(inputs / "references.csv", refs)
    if defect == "missing":
        rows.pop()
    if defect == "duplicate":
        rows.append(rows[0])
    if defect == "identity":
        rows[0]["word"] = "incorrect"
    if defect == "partition":
        rows[0]["fold"] = "1"
    if defect == "probability":
        rows[0]["p_L1"] = "nan"
    if defect == "level":
        rows[0]["baseline"] = "6"
    if defect == "native":
        rows[0]["d1_native"] = "4"
    if defect == "constant3":
        rows[0]["constant3"] = "4"
    write(saved / "predictions.csv", rows)
    if defect != "csv_hash":
        seal_comparison(saved)
    with pytest.raises(ValueError):
        evaluate_d1_ordinal(inputs, inputs / "references.csv", saved, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_inputs_unchanged_manifest_covers_artifacts_and_existing_output_is_protected(tmp_path):
    inputs, saved = source_pack(tmp_path, [0.6, 0, 0, 0, 0.4])
    before = {
        str(p): p.read_bytes()
        for folder in [inputs, saved]
        for p in folder.rglob("*")
        if p.is_file()
    }
    evaluate_d1_ordinal(inputs, inputs / "references.csv", saved, tmp_path / "out")
    for name, digest in json.loads((tmp_path / "out/manifest.json").read_text())[
        "artifacts"
    ].items():
        assert hashlib.sha256((tmp_path / "out" / name).read_bytes()).hexdigest() == digest
    with pytest.raises(FileExistsError):
        evaluate_d1_ordinal(inputs, inputs / "references.csv", saved, tmp_path / "out")
    assert {
        str(p): p.read_bytes()
        for folder in [inputs, saved]
        for p in folder.rglob("*")
        if p.is_file()
    } == before
