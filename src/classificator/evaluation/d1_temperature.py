"""Train-only relative temperature calibration of frozen D1 probability CSVs."""

import csv
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from .d1_calibration import evaluate_d1_calibration
from .dataset import _sha256, _write_csv
from .judge_comparison import _metrics

POLICY = "d1-relative-temperature-v1"
EPSILON = 1e-12
BETA_BOUNDS = (0.05, 20.0)


def _logs(row):
    return [math.log(max(float(row[f"p_L{k}"]), EPSILON)) for k in range(1, 6)]


def _distribution(logs, beta):
    scaled = [beta * value for value in logs]
    peak = max(scaled)
    weights = [math.exp(value - peak) for value in scaled]
    normalizer = math.fsum(weights)
    return [w / normalizer for w in weights], peak + math.log(normalizer)


def _nll(rows, beta):
    return math.fsum(
        _distribution(_logs(row), beta)[1] - beta * _logs(row)[int(row["human_level"]) - 1]
        for row in rows
    ) / len(rows)


def _fit(rows):
    data = [(_logs(r), int(r["human_level"]) - 1) for r in rows]

    def gradient(beta):
        return math.fsum(
            math.fsum(p * v for p, v in zip(_distribution(logs, beta)[0], logs)) - logs[y]
            for logs, y in data
        ) / len(data)

    low, high = BETA_BOUNDS
    if all(max(logs) == min(logs) for logs, _ in data):
        beta, location = 1.0, "flat"
    elif gradient(low) >= 0:
        beta, location = low, "lower_beta_bound"
    elif gradient(high) <= 0:
        beta, location = high, "upper_beta_bound"
    else:
        for _ in range(80):
            middle = (low + high) / 2
            if gradient(middle) < 0:
                low = middle
            else:
                high = middle
        beta, location = (low + high) / 2, "interior"
    return dict(
        train_ids=[r["word_id"] for r in rows],
        train_groups=sorted({r["group"] for r in rows}),
        inverse_temperature=beta,
        temperature=1 / beta,
        location=location,
        training_nll=_nll(rows, beta),
        native_training_nll=_nll(rows, 1),
        floored_training_values=sum(
            float(r[f"p_L{k}"]) < EPSILON for r in rows for k in range(1, 6)
        ),
    )


def _report(rows):
    methods = ["baseline", "d1_native", "d1_calibrated", "d1_temperature"]
    rows = [dict(r, **{k: int(r[k]) for k in [*methods, "human_level"]}) for r in rows]
    report = dict(
        policy=POLICY, cohorts={}, paired={}, probability_metrics={}, automatic_promotion=False
    )
    for cohort in ["150", "50"]:
        group = [r for r in rows if r["cohort"] == cohort]
        subsets = dict(
            all=group,
            **{f"true{k}": [r for r in group if r["human_level"] == k] for k in [1, 4, 5]},
            wordfreq_missing=[r for r in group if not r["wordfreq"] or float(r["wordfreq"]) == 0],
        )
        report["cohorts"][cohort] = {
            m: {name: _metrics(values, m) for name, values in subsets.items()} for m in methods
        }
        report["paired"][cohort] = {
            control: {
                name: dict(
                    severe_avoided=sum(
                        abs(r[control] - r["human_level"]) >= 2
                        and abs(r["d1_temperature"] - r["human_level"]) < 2
                        for r in values
                    ),
                    severe_introduced=sum(
                        abs(r[control] - r["human_level"]) < 2
                        and abs(r["d1_temperature"] - r["human_level"]) >= 2
                        for r in values
                    ),
                )
                for name, values in subsets.items()
            }
            for control in methods[:-1]
        }
        probability = {}
        for name, prefix in [("native", "p"), ("temperature", "q")]:
            losses, briers = [], []
            for r in group:
                beta = 1 if name == "native" else 1 / r["temperature"]
                logs = _logs(r)
                losses.append(_distribution(logs, beta)[1] - beta * logs[r["human_level"] - 1])
                probs = (
                    _distribution(logs, 1)[0]
                    if prefix == "p"
                    else [r[f"q_L{k}"] for k in range(1, 6)]
                )
                briers.append(
                    sum((p - (r["human_level"] == k)) ** 2 for k, p in enumerate(probs, 1))
                )
            probability[name] = dict(
                n=len(group),
                nll=math.fsum(losses) / len(group),
                brier=math.fsum(briers) / len(group),
            )
        probability["floored_values"] = sum(
            float(r[f"p_L{k}"]) < EPSILON for r in group for k in range(1, 6)
        )
        report["probability_metrics"][cohort] = probability
    checks, better = {}, False
    for cohort, methods in report["cohorts"].items():
        for subset in ["all", "true1", "true4", "true5"]:
            a, b = methods["d1_temperature"][subset], methods["baseline"][subset]
            for metric in ["severe", "excess_error_total"]:
                checks[f"{cohort}:{subset}:{metric}"] = a[metric] <= b[metric] if a["n"] else None
                if subset == "all" and a[metric] < b[metric]:
                    better = True
    report["decisions"] = dict(
        baseline_gate=dict(
            passes=all(v is not False for v in checks.values()) and better,
            strict_improvement=better,
            no_regression_checks=checks,
        )
    )
    report["limitations"] = [
        "Temperature is relative to saved probabilities, not a runtime or sampling setting.",
        "NLL fitting does not optimize ordinal severe errors. No class order reversal is possible.",
        "Native probability metrics use fixed epsilon floor and renormalization; native predictions remain original.",
        "150 and risk-selected50 are reused development labels. No true1 in real50; no population estimate.",
        "No automatic promotion, new labels, model calls or database access.",
    ]
    return report


def evaluate_d1_temperature(input_dir, references_csv, output_dir):
    """Frozen v3 CSV inputs -> fold-isolated temperatures, distributions and comparisons."""
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".d1-temperature-") as temporary:
        staged = Path(temporary) / "output"
        staged.mkdir()
        protocol = dict(
            policy=POLICY,
            arm="A",
            epsilon=EPSILON,
            beta_bounds=BETA_BOUNDS,
            objective="mean NLL on train only",
            decoder="lower median; strict survival > 0.5",
            bisection_steps=80,
            flat_beta=1,
            training="frozen grouped CV150; full150 to challenge50",
            inputs={
                str(p.resolve()): _sha256(p)
                for p in [
                    input_dir / "features.csv",
                    input_dir / "inputs.json",
                    Path(references_csv),
                ]
            },
            implementation={p.name: _sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        )
        (staged / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
        evaluate_d1_calibration(input_dir, references_csv, staged / "comparators")
        with (staged / "comparators/predictions.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        pilot = [r for r in rows if r["cohort"] == "150"]
        folds = json.loads((input_dir / "inputs.json").read_text())["folds"]
        fits = {"outer:" + fold: _fit([r for r in pilot if r["fold"] != fold]) for fold in folds}
        fits["full150"] = _fit(pilot)
        for row in rows:
            key = "outer:" + row["fold"] if row["cohort"] == "150" else "full150"
            beta = fits[key]["inverse_temperature"]
            probabilities, _ = _distribution(_logs(row), beta)
            row.update({f"q_L{k}": p for k, p in enumerate(probabilities, 1)})
            row["d1_temperature"] = 1 + sum(sum(probabilities[k:]) > 0.5 for k in range(1, 5))
            row["temperature"] = 1 / beta
        report = _report(rows)
        report["by_fold"] = {
            fold: _report([r for r in rows if r["cohort"] == "50" or r["fold"] == fold])["cohorts"][
                "150"
            ]
            for fold in folds
        }
        (staged / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        _write_csv(staged / "predictions.csv", list(rows[0]), rows)
        severe = [
            r
            for r in rows
            if any(
                abs(int(r[m]) - int(r["human_level"])) >= 2
                for m in ["baseline", "d1_native", "d1_calibrated", "d1_temperature"]
            )
        ]
        _write_csv(staged / "severe-cases.csv", list(rows[0]), severe)
        (staged / "fits.json").write_text(json.dumps(fits, indent=2, allow_nan=False) + "\n")
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
                    artifacts={
                        str(p.relative_to(staged)): _sha256(p)
                        for p in staged.rglob("*")
                        if p.is_file()
                    },
                ),
                indent=2,
            )
            + "\n"
        )
        if any(_sha256(Path(p)) != digest for p, digest in protocol["inputs"].items()):
            raise ValueError("Inputs changed during evaluation")
        staged.rename(output_dir)
    return report
