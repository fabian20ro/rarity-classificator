"""Fixed ordinal excess-error decoding; consumes saved comparisons, never fits."""

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from .d1_calibration import load_d1_evaluation_inputs
from .dataset import _sha256, _write_csv
from .judge_comparison import _indexed, _metrics

POLICY = "d1-fixed-ordinal-excess-v1"
CONTROLS = [
    "baseline",
    "d1_native",
    "d1_calibrated",
    "d1_temperature",
    "d1_class_bias",
    "constant3",
]


def _load(input_dir, references_csv, comparison_dir):
    rows, manifest = load_d1_evaluation_inputs(input_dir, references_csv)
    comparison_dir = Path(comparison_dir)
    frozen = json.loads((comparison_dir / "manifest.json").read_text())
    expected = [
        _sha256(Path(input_dir) / "features.csv"),
        _sha256(Path(input_dir) / "inputs.json"),
        _sha256(Path(references_csv)),
    ]
    if (
        frozen["policy"] != "d1-regularized-class-bias-v1"
        or sorted(frozen["inputs"].values()) != sorted(expected)
        or frozen["artifacts"]["predictions.csv"] != _sha256(comparison_dir / "predictions.csv")
    ):
        raise ValueError("Frozen comparison provenance mismatch")
    saved = _indexed(
        comparison_dir / "predictions.csv",
        {
            "word",
            "cohort",
            "group",
            "fold",
            "wordfreq",
            "historical_baseline",
            "human_level",
            *CONTROLS,
            *[f"p_L{k}" for k in range(1, 6)],
        },
    )
    if set(saved) != {r["word_id"] for r in rows}:
        raise ValueError("Comparison must cover every frozen form exactly")
    for row in rows:
        other = saved[row["word_id"]]
        if any(other[k] != row[k] for k in ["word", "cohort", "group", "fold"]):
            raise ValueError("Comparison form or partition mismatch")
        for k in ["human_level", "historical_baseline", *CONTROLS]:
            if other[k] not in {"1", "2", "3", "4", "5"}:
                raise ValueError("Invalid comparator level")
        if (
            any(
                int(other[k]) != row[k] for k in ["human_level", "historical_baseline", "d1_native"]
            )
            or other["constant3"] != "3"
        ):
            raise ValueError("Comparison reference or native prediction mismatch")
        if (
            any(float(other[f"p_L{k}"]) != float(row[f"p_L{k}"]) for k in range(1, 6))
            or (float(other["wordfreq"]) if other["wordfreq"] else None) != row["wordfreq"]
        ):
            raise ValueError("Comparison feature mismatch")
    return sorted(saved.values(), key=lambda r: (r["cohort"] != "150", int(r["word_id"]))), manifest


def _subsets(rows):
    return dict(
        all=rows,
        **{f"true{k}": [r for r in rows if r["human_level"] == k] for k in [1, 4, 5]},
        wordfreq_missing=[r for r in rows if not r["wordfreq"] or float(r["wordfreq"]) == 0],
    )


def _gate(cohorts, control):
    checks, better = {}, False
    for cohort, methods in cohorts.items():
        for subset in ["all", "true1", "true4", "true5"]:
            a, b = methods["d1_ordinal"][subset], methods[control][subset]
            for metric in ["severe", "excess_error_total"]:
                checks[f"{cohort}:{subset}:{metric}"] = a[metric] <= b[metric] if a["n"] else None
                if subset == "all" and a[metric] < b[metric]:
                    better = True
    return dict(
        passes=all(v is not False for v in checks.values()) and better,
        strict_improvement=better,
        no_regression_checks=checks,
    )


def _report(rows, folds):
    methods = [*CONTROLS, "d1_ordinal"]
    rows = [dict(r, **{k: int(r[k]) for k in [*methods, "human_level"]}) for r in rows]
    report = dict(
        policy=POLICY,
        cohorts={},
        paired={},
        estimated_risk={},
        fitted_parameters=0,
        automatic_promotion=False,
    )
    for cohort in ["150", "50"]:
        group = [r for r in rows if r["cohort"] == cohort]
        subsets = _subsets(group)
        report["cohorts"][cohort] = {
            m: {s: _metrics(values, m) for s, values in subsets.items()} for m in methods
        }
        report["paired"][cohort] = {
            control: {
                s: dict(
                    severe_avoided=sum(
                        abs(r[control] - r["human_level"]) >= 2
                        and abs(r["d1_ordinal"] - r["human_level"]) < 2
                        for r in values
                    ),
                    severe_introduced=sum(
                        abs(r[control] - r["human_level"]) < 2
                        and abs(r["d1_ordinal"] - r["human_level"]) >= 2
                        for r in values
                    ),
                )
                for s, values in subsets.items()
            }
            for control in CONTROLS
        }
        report["estimated_risk"][cohort] = {
            m: math.fsum(r[f"ordinal_risk_L{r[m]}"] for r in group) / len(group)
            for m in ["d1_native", "constant3", "d1_ordinal"]
        }
    report["decisions"] = {
        control + "_gate": _gate(report["cohorts"], control)
        for control in ["baseline", "constant3"]
    }
    report["by_fold"] = {
        fold: {
            m: _metrics([r for r in rows if r["cohort"] == "150" and r["fold"] == fold], m)
            for m in methods
        }
        for fold in folds
    }
    report["limitations"] = [
        "Minimizes expected excess beyond tolerance1, not binary probability of an error>=2.",
        "Expected costs rely on D1 probabilities, not validated confidence estimates.",
        "Ordinal decoder uses native probabilities only; all comparators frozen, no fit or tuning.",
        "Reused development150 and risk-selected50, no true1 in real50; no population estimate.",
        "No automatic promotion, new labels, model calls or database access.",
    ]
    return report


def evaluate_d1_ordinal(input_dir, references_csv, comparison_dir, output_dir):
    """Frozen feature/reference CSVs + saved comparisons -> label-free ordinal decisions."""
    output_dir = Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    sources = [
        Path(input_dir) / "features.csv",
        Path(input_dir) / "inputs.json",
        Path(references_csv),
        Path(comparison_dir) / "predictions.csv",
        Path(comparison_dir) / "manifest.json",
    ]
    hashes = {str(p.resolve()): _sha256(p) for p in sources}
    rows, manifest = _load(input_dir, references_csv, comparison_dir)
    protocol = dict(
        policy=POLICY,
        arm="A",
        distribution="native",
        fitted_parameters=0,
        loss="max(abs(action-label)-1,0)",
        tie_tolerance=1e-12,
        tie_break="closest to existing native lower median, then lower action",
        probability_preparation="normalize validated vector to sum1; no floor",
        cohort_sizes=manifest["cohort_sizes"],
        folds=manifest["folds"],
        inputs=hashes,
        implementation={p.name: _sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
    )
    for row in rows:
        p = [float(row[f"p_L{k}"]) for k in range(1, 6)]
        total = math.fsum(p)
        p = [v / total for v in p]
        risks = [
            math.fsum(prob * max(abs(k - y) - 1, 0) for y, prob in enumerate(p, 1))
            for k in range(1, 6)
        ]
        candidates = [k for k in range(1, 6) if risks[k - 1] <= min(risks) + 1e-12]
        row["d1_ordinal"] = min(candidates, key=lambda k: (abs(k - int(row["d1_native"])), k))
        row.update({f"ordinal_risk_L{k}": v for k, v in enumerate(risks, 1)})
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".d1-ordinal-") as temporary:
        staged = Path(temporary) / "output"
        staged.mkdir()
        report = _report(rows, manifest["folds"])
        for name, value in [("protocol.json", protocol), ("report.json", report)]:
            (staged / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        _write_csv(staged / "predictions.csv", list(rows[0]), rows)
        severe = [
            r
            for r in rows
            if any(abs(int(r[m]) - int(r["human_level"])) >= 2 for m in [*CONTROLS, "d1_ordinal"])
        ]
        _write_csv(staged / "severe-cases.csv", list(rows[0]), severe)
        if any(_sha256(Path(path)) != digest for path, digest in hashes.items()):
            raise ValueError("Inputs changed during evaluation")
        (staged / "manifest.json").write_text(
            json.dumps(
                dict(
                    policy=POLICY,
                    inputs=hashes,
                    artifacts={p.name: _sha256(p) for p in staged.iterdir()},
                ),
                indent=2,
            )
            + "\n"
        )
        staged.rename(output_dir)
    return report
