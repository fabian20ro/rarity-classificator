"""Offline grouped calibration of saved D1 Score distributions, never model/DB I/O."""

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _sha256, _write_csv, _game_key
from .frequency_calibration import _fit as fit_frequency
from .judge_comparison import _indexed, _metrics

POLICY = "d1-monotone-affine-v3"
METHODS = [
    "historical_baseline",
    "baseline",
    "d1_native",
    "d1_calibrated",
    "baseline_calibrated",
    "combined",
    "constant3",
]


def _affine(rows, features):
    # At most two predictors. Enumerate active sets for nonnegative least squares
    # with an unconstrained intercept; constants/collinearity use simpler sets.
    n = len(rows)
    means = {f: sum(r[f] for r in rows) / n for f in features}
    target = sum(r["human_level"] for r in rows) / n
    variance = {f: sum((r[f] - means[f]) ** 2 for r in rows) for f in features}
    covariance = {
        f: sum((r[f] - means[f]) * (r["human_level"] - target) for r in rows) for f in features
    }
    candidates = [{f: 0.0 for f in features}]
    for f in features:
        if variance[f] > 0:
            candidates.append(
                {g: max(0.0, covariance[f] / variance[f]) if g == f else 0.0 for g in features}
            )
    if len(features) == 2:
        a, b = features
        cross = sum((r[a] - means[a]) * (r[b] - means[b]) for r in rows)
        determinant = variance[a] * variance[b] - cross * cross
        if determinant > 1e-12 * variance[a] * variance[b]:
            slopes = {
                a: (covariance[a] * variance[b] - covariance[b] * cross) / determinant,
                b: (covariance[b] * variance[a] - covariance[a] * cross) / determinant,
            }
            if all(value >= 0 for value in slopes.values()):
                candidates.append(slopes)
    fitted = []
    for slopes in candidates:
        intercept = target - sum(slopes[f] * means[f] for f in features)
        loss = sum(
            (r["human_level"] - intercept - sum(slopes[f] * r[f] for f in features)) ** 2
            for r in rows
        )
        fitted.append(dict(intercept=intercept, coefficients=slopes, training_squared_error=loss))
    minimum = min(m["training_squared_error"] for m in fitted)
    tied = [m for m in fitted if m["training_squared_error"] <= minimum + 1e-12 * max(1, minimum)]
    return min(
        tied,
        key=lambda m: (
            sum(v > 0 for v in m["coefficients"].values()),
            tuple(-m["coefficients"][f] for f in features),
        ),
    )


def _predict(model, row):
    value = model["intercept"] + sum(b * row[f] for f, b in model["coefficients"].items())
    # Explicit lower tie, unlike Python banker's rounding.
    return max(1, min(5, math.ceil(value - 0.5)))


def _run_split(train, heldout):
    observed = [(r["wordfreq"], r["human_level"]) for r in train if r["wordfreq"]]
    frequency = fit_frequency(observed) if observed else None

    def baseline(row):
        return (
            1 + sum(row["wordfreq"] < t for t in frequency["thresholds"])
            if row["wordfreq"] and frequency
            else 4
        )

    training = [dict(r, baseline=baseline(r)) for r in train]
    models = dict(
        d1_calibrated=_affine(training, ["d1_expected"]),
        baseline_calibrated=_affine(training, ["baseline"]),
        combined=_affine(training, ["baseline", "d1_expected"]),
    )
    predictions = []
    for row in heldout:
        row = dict(row, baseline=baseline(row), constant3=3)
        row.update({name: _predict(model, row) for name, model in models.items()})
        predictions.append(row)
    return predictions, dict(
        train_ids=[r["word_id"] for r in train],
        train_groups=sorted({r["group"] for r in train}),
        frequency=frequency,
        models=models,
    )


def load_d1_evaluation_inputs(input_dir, references_csv):
    """Validate frozen evaluation CSVs without fitting or changing any data."""
    input_dir = Path(input_dir)
    manifest = json.loads((input_dir / "inputs.json").read_text())
    if (
        manifest["policy"] != POLICY
        or manifest["arm"] != "A"
        or manifest["features_sha256"] != _sha256(input_dir / "features.csv")
    ):
        raise ValueError("Frozen feature manifest mismatch")
    features = _indexed(
        input_dir / "features.csv",
        {
            "word",
            "cohort",
            "group",
            "fold",
            "wordfreq",
            "historical_baseline",
            *[f"p_L{i}" for i in range(1, 6)],
        },
    )
    references = _indexed(Path(references_csv), {"word", "human_level"})
    if set(features) != set(references):
        raise ValueError("References must cover every frozen feature ID")
    if (
        set(manifest.get("cohort_sizes", {})) != {"150", "50"}
        or any(type(n) is not int or n <= 0 for n in manifest["cohort_sizes"].values())
        or any(
            sum(r["cohort"] == c for r in features.values()) != n
            for c, n in manifest["cohort_sizes"].items()
        )
    ):
        raise ValueError("Frozen cohort sizes mismatch")
    folds = manifest["folds"]
    if (
        len(folds) < 2
        or len(set(folds)) != len(folds)
        or any(not isinstance(f, str) or not f.isdigit() for f in folds)
        or set(folds) != {r["fold"] for r in features.values() if r["cohort"] == "150"}
    ):
        raise ValueError("Invalid frozen folds")
    rows = []
    partitions, families = {}, {}
    for wid, row in features.items():
        if set(row) != {
            "word_id",
            "word",
            "cohort",
            "group",
            "fold",
            "wordfreq",
            "historical_baseline",
            *[f"p_L{i}" for i in range(1, 6)],
        } or set(references[wid]) != {"word_id", "word", "human_level"}:
            raise ValueError("Unexpected fields; labels forbidden in features")
        if (
            not row["word"].strip()
            or not row["group"].strip()
            or row["cohort"] not in {"150", "50"}
            or (row["cohort"] == "50" and row["fold"] != "")
            or row["historical_baseline"] not in {"1", "2", "3", "4", "5"}
            or references[wid]["human_level"] not in {"1", "2", "3", "4", "5"}
        ):
            raise ValueError("Invalid level or partition")
        key = _game_key(row["word"])
        if key in families and families[key] != (row["cohort"], row["group"]):
            raise ValueError("Orthographic family crosses groups/cohorts")
        families[key] = (row["cohort"], row["group"])
        if references[wid]["word"] != row["word"]:
            raise ValueError("Exact form identity mismatch")
        partition = (row["cohort"], row["fold"])
        if row["group"] in partitions and partitions[row["group"]] != partition:
            raise ValueError("Lexical group crosses folds/cohorts")
        partitions[row["group"]] = partition
        p = [float(row[f"p_L{i}"]) for i in range(1, 6)]
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in p) or not math.isclose(
            sum(p), 1, abs_tol=1e-6
        ):
            raise ValueError("Invalid native probability distribution")
        frequency = float(row["wordfreq"]) if row["wordfreq"] else None
        if frequency is not None and (not math.isfinite(frequency) or not 0 <= frequency <= 1):
            raise ValueError("Invalid exact-form frequency")
        rows.append(
            dict(
                row,
                human_level=int(references[wid]["human_level"]),
                historical_baseline=int(row["historical_baseline"]),
                wordfreq=float(row["wordfreq"]) if row["wordfreq"] else None,
                d1_expected=sum(i * v for i, v in enumerate(p, 1)),
                d1_native=1 + sum(sum(p[k:]) > 0.5 for k in range(1, 5)),
            )
        )
    rows.sort(key=lambda r: int(r["word_id"]))
    return rows, manifest


def evaluate_d1_calibration(input_dir, references_csv, output_dir):
    """Frozen feature CSV + references -> OOF150 / full150-to50 CSVs and fit ledger."""
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    rows, manifest = load_d1_evaluation_inputs(input_dir, references_csv)
    pilot = [r for r in rows if r["cohort"] == "150"]
    challenge = [r for r in rows if r["cohort"] == "50"]
    fits, predictions = {}, []
    for fold in manifest["folds"]:
        result, fitted = _run_split(
            [r for r in pilot if r["fold"] != fold], [r for r in pilot if r["fold"] == fold]
        )
        predictions.extend(result)
        fits["outer:" + fold] = fitted
    result, fits["full150"] = _run_split(pilot, challenge)
    predictions.extend(result)
    predictions.sort(key=lambda r: (r["cohort"] != "150", int(r["word_id"])))
    report = dict(policy=POLICY, cohorts={}, paired={}, decisions={}, automatic_promotion=False)
    for cohort in ["150", "50"]:
        group = [r for r in predictions if r["cohort"] == cohort]
        subsets = dict(
            all=group,
            **{f"true{k}": [r for r in group if r["human_level"] == k] for k in [1, 4, 5]},
            wordfreq_missing=[r for r in group if not r["wordfreq"]],
        )
        report["paired"][cohort] = {
            m: {
                name: dict(
                    severe_avoided=sum(
                        abs(r["baseline"] - r["human_level"]) >= 2
                        and abs(r[m] - r["human_level"]) < 2
                        for r in values
                    ),
                    severe_introduced=sum(
                        abs(r["baseline"] - r["human_level"]) < 2
                        and abs(r[m] - r["human_level"]) >= 2
                        for r in values
                    ),
                )
                for name, values in subsets.items()
            }
            for m in ["d1_calibrated", "baseline_calibrated", "combined"]
        }
        report["cohorts"][cohort] = {
            m: {name: _metrics(values, m) for name, values in subsets.items()} for m in METHODS
        }

    def gate(candidate, control):
        checks = {}
        better = False
        for cohort, methods in report["cohorts"].items():
            for subset in ["all", "true1", "true4", "true5"]:
                for metric in ["severe", "excess_error_total"]:
                    a, b = methods[candidate][subset], methods[control][subset]
                    checks[f"{cohort}:{subset}:{metric}"] = (
                        a[metric] <= b[metric] if a["n"] else None
                    )
                    if subset == "all" and a[metric] < b[metric]:
                        better = True
        return dict(
            passes=all(v is not False for v in checks.values()) and better,
            strict_improvement=better,
            no_regression_checks=checks,
        )

    for candidate in ["d1_calibrated", "baseline_calibrated", "combined"]:
        primary = gate(candidate, "baseline")
        added = gate(candidate, "baseline_calibrated")
        report["decisions"][candidate] = dict(
            passes_vs_baseline=primary["passes"],
            adds_value_vs_baseline_calibrated=added["passes"],
            baseline_gate=primary,
            added_value_gate=added,
        )
    report["by_fold"] = {
        fold: {
            m: _metrics([r for r in predictions if r["cohort"] == "150" and r["fold"] == fold], m)
            for m in METHODS
        }
        for fold in manifest["folds"]
    }
    report["limitations"] = [
        "Reused development labels; 50 is an explored risk-selected challenge set, not independent validation.",
        "Wordfreq thresholds refitted inside each outer training fold; historical LOGO baseline is descriptive only.",
        "Meta-training baseline covariates are in-sample for the outer training set; all reported150 predictions remain out-of-fold.",
        "Squared-error fit and nonnegative coefficients fixed before results; no parameter search or loss tuning.",
        "No automatic promotion, new labels, model calls or database access.",
    ]
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".d1-calibration-") as temporary:
        staged = Path(temporary) / "output"
        staged.mkdir()
        _write_csv(staged / "predictions.csv", list(predictions[0]), predictions)
        for name, value in [("fits.json", fits), ("report.json", report)]:
            (staged / name).write_text(
                json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
            )
        (staged / "manifest.json").write_text(
            json.dumps(
                dict(
                    policy=POLICY,
                    inputs={
                        str(p.resolve()): _sha256(p)
                        for p in [
                            input_dir / "features.csv",
                            input_dir / "inputs.json",
                            Path(references_csv),
                        ]
                    },
                    implementation_sha256=_sha256(Path(__file__)),
                    artifacts={p.name: _sha256(p) for p in staged.iterdir()},
                ),
                indent=2,
            )
            + "\n"
        )
        staged.rename(output_dir)
    return report
