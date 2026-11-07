"""Prepare and evaluate frozen D1-A artifacts offline; no inference or DB connection.

PYTHONPATH=src python scripts/run_d1_calibration.py DATA_ROOT NEW_OUTPUT_DIRECTORY
"""

import csv
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

from classificator.evaluation.d1_calibration import evaluate_d1_calibration, POLICY
from classificator.evaluation.dataset import _game_key


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    with path.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def run(data_root, output_dir):
    data_root, output_dir = Path(data_root).resolve(), Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(output_dir)
    prior = data_root / "score-v2-2026-11-07"
    audit = json.loads((prior / "audit.json").read_text())
    assert audit["status"] == "PASS" and audit["valid_receipts"] == 800
    assert audit["protocol_sha256"] == sha(prior / "protocol.json")
    for name, digest in json.loads((prior / "protocol.json").read_text())["inputs"].items():
        assert sha(prior / name) == digest, name
    for name, digest in json.loads((prior / "protected-inputs.json").read_text()).items():
        assert sha(name) == digest, name
    source_paths = [
        prior / "analysis-only/reference.csv",
        data_root / "omni-few-shot-2026-10-30/inputs/folds.csv",
        data_root / "omni-few-shot-2026-10-30/inputs/baseline-oof.csv",
        data_root / "independent-1000-2026-10-30/signals.csv",
        prior / "protocol.json",
        prior / "audit.json",
    ]
    sources = {str(p): sha(p) for p in source_paths}
    references = read(source_paths[0])
    assert len(references) == 200
    assert len({r["word_id"] for r in references}) == 200
    folds = {r["word_id"]: r for r in read(source_paths[1])}
    pilot_frequency = {r["word_id"]: r for r in read(source_paths[2])}
    new_frequency = {r["form_id"]: r for r in read(source_paths[3])}
    features, labels = [], []
    for cohort in ["150", "50"]:
        rows = [r for r in references if r["cohort"] == cohort]
        assert len(rows) == int(cohort)
        campaign = prior / "campaigns" / cohort / "A"
        manifest = json.loads((campaign / "manifest.json").read_text())
        assert sha(campaign / "manifest.json") == audit["campaign_manifests"][cohort + "/A"]
        assert manifest["config"]["runtime"]["protocol_sha256"] == sha(prior / "protocol.json")
        sources[str(campaign / "manifest.json")] = sha(campaign / "manifest.json")
        sources[str(campaign / "predictions.csv")] = sha(campaign / "predictions.csv")
        predicted = {r["word_id"]: r for r in read(campaign / "predictions.csv")}
        assert set(predicted) == {r["word_id"] for r in rows}
        for row in sorted(rows, key=lambda r: int(r["word_id"])):
            wid = row["word_id"]
            prediction = predicted[wid]
            receipt_path = campaign / "records" / f"{wid}.json"
            sources[str(receipt_path)] = sha(receipt_path)
            receipt = json.loads(receipt_path.read_text())
            request = receipt["request"]
            assert receipt["status"] == prediction["status"] == "scored"
            assert (
                str(receipt["word_id"]) == wid
                and receipt["word"] == prediction["word"] == row["word"]
            )
            assert request["questions"] == {"rarity": manifest["config"]["question"]}
            native = json.loads(receipt["response"])["answers"]["rarity"]
            assert native["type"] == "score"
            assert native["legend"] == {
                str(i): value for i, value in enumerate(manifest["config"]["question"]["criteria"])
            }
            probabilities = {f"p_L{i + 1}": native["probabilities"][str(i)] for i in range(5)}
            assert all(float(prediction[k]) == v for k, v in probabilities.items())
            frequency = (pilot_frequency if cohort == "150" else new_frequency)[wid]
            assert frequency["word"] == row["word"]
            group = (
                folds[wid]["group"] if cohort == "150" else "challenge:" + _game_key(row["word"])
            )
            fold = folds[wid]["fold"] if cohort == "150" else ""
            features.append(
                dict(
                    word_id=wid,
                    word=row["word"],
                    cohort=cohort,
                    group=group,
                    fold=fold,
                    wordfreq=frequency["wordfreq"],
                    historical_baseline=row["baseline_level"],
                    **probabilities,
                )
            )
            labels.append(dict(word_id=wid, word=row["word"], human_level=row["human_level"]))
    output_dir.mkdir(parents=True)
    inputs = output_dir / "inputs"
    inputs.mkdir()
    write(inputs / "features.csv", features)
    write(inputs / "references.csv", labels)
    save(
        inputs / "inputs.json",
        dict(
            schema=1,
            policy=POLICY,
            arm="A",
            cohort_sizes={"150": 150, "50": 50},
            folds=["0", "1", "2", "3", "4"],
            features_sha256=sha(inputs / "features.csv"),
        ),
    )
    code = Path(__file__).resolve().parent.parent
    implementation = {
        str(p): sha(p)
        for p in [
            Path(__file__),
            *[
                code / "src/classificator/evaluation" / name
                for name in [
                    "d1_calibration.py",
                    "frequency_calibration.py",
                    "judge_comparison.py",
                    "dataset.py",
                ]
            ],
        ]
    }
    # Written BEFORE fitting/metrics; no later protocol tuning.
    protocol = dict(
        schema=1,
        policy=POLICY,
        arm="A",
        cohort_sizes={"150": 150, "50": 50},
        inputs={str(p): sha(p) for p in inputs.iterdir()},
        sources=sources,
        implementation=implementation,
        fit="Least squares affine intercept + nonnegative coefficients; no hyperparameter selection.",
        features={
            "d1_calibrated": ["native expected level"],
            "baseline_calibrated": ["fold-refitted baseline"],
            "combined": ["fold-refitted baseline", "native expected level"],
        },
        baseline="Existing wordfreq MAE grid fit on ALL observed training labels; missing/unfitted=>4. Refit per outer train, then full150 for50.",
        training="Frozen5groupfold150; meta-training baseline features in-sample outertrain. Full150fit for50; no50labels in fit.",
        numerical_policy="Active subsets0/1/2 predictors; collinearity determinant tolerance1e-12; loss tie tolerance1e-12; prefer fewer nonzero terms then baseline coefficient.",
        output="Clamp1..5, nearest integer, lower exact half tie; no calibrated confidence claims.",
        gate="For both cohorts, no greater severe count or excess overall and separately true1/4/5, strict overall improvement at leastone cohort. Combined must also pass against calibratedbaseline.",
        primary_metrics=["error>=2", "sum(max(abs(error)-1,0))"],
        limitations=[
            "Previously explored150/50; no independent or population accuracy estimate.",
            "Historical baseline11/13 descriptive only; primary comparator refitted5fold/full150.",
            "50 risk-selected and lacks true1. No automatic promotion.",
        ],
    )
    save(output_dir / "protocol.json", protocol)
    with (
        patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")),
        patch("socket.socket.connect_ex", side_effect=AssertionError("Network forbidden")),
        patch("subprocess.Popen", side_effect=AssertionError("Subprocess forbidden")),
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
    ):
        report = evaluate_d1_calibration(
            inputs, inputs / "references.csv", output_dir / "evaluation"
        )
    for name, digest in sources.items():
        assert sha(name) == digest, name
    save(
        output_dir / "verification.json",
        dict(
            status="PASS",
            sources_unchanged=len(sources),
            network_and_db_blocked=True,
            cohort_sizes={"150": 150, "50": 50},
            protocol_sha256=sha(output_dir / "protocol.json"),
        ),
    )
    for cohort, methods in report["cohorts"].items():
        print(
            cohort,
            {
                m: dict(
                    severe=v["all"]["severe"],
                    excess=v["all"]["excess_error_total"],
                    true1=v["true1"]["severe"],
                    true4=v["true4"]["severe"],
                    true5=v["true5"]["severe"],
                )
                for m, v in methods.items()
            },
        )
    print(
        "Decisions",
        {
            m: (v["passes_vs_baseline"], v["adds_value_vs_baseline_calibrated"])
            for m, v in report["decisions"].items()
        },
    )


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
