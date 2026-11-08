"""Regularized class offsets, selected entirely inside grouped training folds."""

import csv
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from .d1_temperature import evaluate_d1_temperature
from .dataset import _sha256, _write_csv
from .judge_comparison import _metrics

POLICY = "d1-regularized-class-bias-v1"
EPSILON = 1e-12
LAMBDAS = [None, 10.0, 1.0, 0.1, 0.01]  # None = identity, strongest regularization.


def _logits(row):
    return [math.log(max(float(row[f"p_L{k}"]), EPSILON)) for k in range(1, 6)]


def _probabilities(logits, bias):
    z = [v + b for v, b in zip(logits, bias)]
    peak = max(z)
    exp = [math.exp(v - peak) for v in z]
    total = math.fsum(exp)
    return [v / total for v in exp], peak + math.log(total)


def _loss(rows, bias):
    return math.fsum(
        _probabilities(_logits(r), bias)[1]
        - _logits(r)[int(r["human_level"]) - 1]
        - bias[int(r["human_level"]) - 1]
        for r in rows
    ) / len(rows)


def _fit(rows, penalty):
    data = [(_logits(r), int(r["human_level"]) - 1) for r in rows]
    bias = [0.0] * 5
    residual, iteration = 0.0, 0
    if penalty is not None:
        for iteration in range(10001):
            sums = [0.0] * 5
            for logits, y in data:
                p, _ = _probabilities(logits, bias)
                for k in range(5):
                    sums[k] += p[k] - (k == y)
            gradient = [s / len(data) + penalty * b for s, b in zip(sums, bias)]
            residual = max(abs(v) for v in gradient)
            if residual <= 1e-9:
                break
            if iteration == 10000:
                raise ValueError("Class-bias solver failed to converge")
            bias = [b - g / (0.5 + penalty) for b, g in zip(bias, gradient)]
            mean = math.fsum(bias) / 5
            bias = [b - mean for b in bias]
    loss = _loss(rows, bias)
    return dict(
        lambda_=penalty,
        bias=bias,
        training_nll=loss,
        penalized_objective=loss + (penalty or 0) / 2 * sum(b * b for b in bias),
        gradient_max=residual if penalty is not None else None,
        iterations=iteration,
        train_ids=[r["word_id"] for r in rows],
        train_groups=sorted({r["group"] for r in rows}),
    )


def _select(train):
    folds = sorted({r["fold"] for r in train})
    candidates = []
    for penalty in LAMBDAS:
        splits, total_loss = {}, 0.0
        for fold in folds:
            fitting = [r for r in train if r["fold"] != fold]
            validation = [r for r in train if r["fold"] == fold]
            fitted = _fit(fitting, penalty)
            loss = _loss(validation, fitted["bias"])
            total_loss += loss * len(validation)
            splits[fold] = dict(
                fit=fitted, validation_ids=[r["word_id"] for r in validation], validation_nll=loss
            )
        candidates.append(dict(lambda_=penalty, inner_nll=total_loss / len(train), splits=splits))
    minimum = min(c["inner_nll"] for c in candidates)
    chosen = next(c for c in candidates if c["inner_nll"] <= minimum + 1e-10)
    return dict(
        selected_lambda=chosen["lambda_"],
        selection_nll=chosen["inner_nll"],
        candidates=candidates,
        fit=_fit(train, chosen["lambda_"]),
    )


def _report(rows, report):
    methods = ["baseline", "d1_native", "d1_calibrated", "d1_temperature"]
    rows = [
        dict(r, **{k: int(r[k]) for k in [*methods, "d1_class_bias", "human_level"]}) for r in rows
    ]
    report["policy"] = POLICY
    report["paired"] = {}
    for cohort in ["150", "50"]:
        group = [r for r in rows if r["cohort"] == cohort]
        subsets = dict(
            all=group,
            **{f"true{k}": [r for r in group if r["human_level"] == k] for k in [1, 4, 5]},
            wordfreq_missing=[r for r in group if not r["wordfreq"] or float(r["wordfreq"]) == 0],
        )
        report["cohorts"][cohort]["d1_class_bias"] = {
            name: _metrics(values, "d1_class_bias") for name, values in subsets.items()
        }
        report["paired"][cohort] = {
            control: {
                name: dict(
                    severe_avoided=sum(
                        abs(r[control] - r["human_level"]) >= 2
                        and abs(r["d1_class_bias"] - r["human_level"]) < 2
                        for r in values
                    ),
                    severe_introduced=sum(
                        abs(r[control] - r["human_level"]) < 2
                        and abs(r["d1_class_bias"] - r["human_level"]) >= 2
                        for r in values
                    ),
                )
                for name, values in subsets.items()
            }
            for control in methods
        }
        report["probability_metrics"][cohort]["class_bias"] = dict(
            n=len(group),
            nll=math.fsum(r["bias_nll"] for r in group) / len(group),
            brier=math.fsum(
                sum((r[f"bias_p_L{k}"] - (r["human_level"] == k)) ** 2 for k in range(1, 6))
                for r in group
            )
            / len(group),
        )
    checks, better = {}, False
    for cohort, methods in report["cohorts"].items():
        for subset in ["all", "true1", "true4", "true5"]:
            a, b = methods["d1_class_bias"][subset], methods["baseline"][subset]
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
    for fold, values in report["by_fold"].items():
        group = [r for r in rows if r["cohort"] == "150" and r["fold"] == fold]
        subsets = dict(
            all=group,
            **{f"true{k}": [r for r in group if r["human_level"] == k] for k in [1, 4, 5]},
            wordfreq_missing=[r for r in group if not r["wordfreq"] or float(r["wordfreq"]) == 0],
        )
        values["d1_class_bias"] = {
            name: _metrics(values, "d1_class_bias") for name, values in subsets.items()
        }
    report["limitations"] = [
        "Bias changes class rankings; temperature fixed1, no joint scaling fit.",
        "Lambda selection uses pooled inner OOF NLL only. NLL is not ordinal severe-error cost.",
        "Native predictions unchanged; identity uses fixed probability floor and normalization.",
        "Reused development150 and risk-selected50; no true1 in real50, no population estimate.",
        "No automatic promotion, model calls, new labels or database access.",
    ]
    return report


def evaluate_d1_class_bias(input_dir, references_csv, output_dir):
    """Frozen CSV inputs -> nested OOF150 and train150-to50 bias comparison."""
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".d1-class-bias-") as temporary:
        staged = Path(temporary) / "output"
        staged.mkdir()
        protocol = dict(
            policy=POLICY,
            arm="A",
            epsilon=EPSILON,
            temperature=1,
            lambdas_strongest_first=LAMBDAS,
            objective="mean NLL + lambda/2 * sum(bias**2)",
            selection="pooled inner grouped OOF NLL; tie1e-10 chooses stronger regularization",
            solver="centered gradient descent, step1/(.5+lambda), gradient max1e-9, limit10000",
            decoder="lower median; strict survival > .5",
            training="outer grouped CV150 with nested inner CV; full150-selected fit for50",
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
        evaluate_d1_temperature(input_dir, references_csv, staged / "comparators")
        with (staged / "comparators/predictions.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        pilot = [r for r in rows if r["cohort"] == "150"]
        folds = json.loads((input_dir / "inputs.json").read_text())["folds"]
        if len(folds) < 3:
            raise ValueError("Nested class-bias selection requires at least three folds")
        fits = {"outer:" + fold: _select([r for r in pilot if r["fold"] != fold]) for fold in folds}
        fits["full150"] = _select(pilot)
        for row in rows:
            fitted = fits["outer:" + row["fold"] if row["cohort"] == "150" else "full150"]
            p, normalizer = _probabilities(_logits(row), fitted["fit"]["bias"])
            row.update({f"bias_p_L{k}": v for k, v in enumerate(p, 1)})
            row["d1_class_bias"] = 1 + sum(sum(p[k:]) > 0.5 for k in range(1, 5))
            row["selected_lambda"] = (
                fitted["selected_lambda"] if fitted["selected_lambda"] is not None else "identity"
            )
            y = int(row["human_level"]) - 1
            row["bias_nll"] = normalizer - _logits(row)[y] - fitted["fit"]["bias"][y]
        report = _report(rows, json.loads((staged / "comparators/report.json").read_text()))
        (staged / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        _write_csv(staged / "predictions.csv", list(rows[0]), rows)
        severe = [
            r
            for r in rows
            if any(
                abs(int(r[m]) - int(r["human_level"])) >= 2
                for m in [
                    "baseline",
                    "d1_native",
                    "d1_calibrated",
                    "d1_temperature",
                    "d1_class_bias",
                ]
            )
        ]
        _write_csv(staged / "severe-cases.csv", list(rows[0]), severe)
        (staged / "fits.json").write_text(json.dumps(fits, indent=2, allow_nan=False) + "\n")
        if any(_sha256(Path(p)) != digest for p, digest in protocol["inputs"].items()):
            raise ValueError("Inputs changed during evaluation")
        (staged / "manifest.json").write_text(
            json.dumps(
                dict(
                    policy=POLICY,
                    inputs=protocol["inputs"],
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
        staged.rename(output_dir)
    return report
