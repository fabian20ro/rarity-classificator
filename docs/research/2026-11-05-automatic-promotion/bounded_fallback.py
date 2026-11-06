"""Offline paired comparison using the frozen evaluation rows produced by run.py."""

import argparse
import json
from pathlib import Path

from classificator.evaluation.dataset import _read_csv, _sha256, _write_csv
from classificator.evaluation.judge_comparison import _level

HERE = Path(__file__).resolve().parent


def compare(row):
    previous = _level(row["previous"])
    baseline = _level(row["prediction"])
    gold = _level(row["human_level"])
    keep = row["route"] == "fallback" and abs(previous - baseline) >= 2
    proposed = previous if keep else baseline
    old_error = abs(baseline - gold)
    new_error = abs(proposed - gold)
    return dict(
        **row,
        kept_previous=keep,
        proposed=proposed,
        baseline_error=old_error,
        rule_error=new_error,
        severe_avoided=old_error >= 2 > new_error,
        useful_correction_lost=new_error >= 2 > old_error,
    )


def summarize(rows):
    old = [r["baseline_error"] for r in rows]
    new = [r["rule_error"] for r in rows]
    return dict(
        n=len(rows),
        kept_previous=sum(r["kept_previous"] for r in rows),
        severe_before=sum(e >= 2 for e in old),
        severe_after=sum(e >= 2 for e in new),
        avoided=sum(r["severe_avoided"] for r in rows),
        lost=sum(r["useful_correction_lost"] for r in rows),
        cost_before=sum(max(0, e - 1) for e in old),
        cost_after=sum(max(0, e - 1) for e in new),
        closer=sum(a < b for a, b in zip(new, old)),
        farther=sum(a > b for a, b in zip(new, old)),
        equal_error=sum(a == b for a, b in zip(new, old)),
    )


def run(evaluations, output):
    expected = json.loads((HERE / "manifest.json").read_text())["artifacts"][
        "evaluations.csv"
    ]
    if _sha256(evaluations) != expected:
        raise ValueError(
            "Expected the frozen paired evaluation CSV from the route simulation"
        )
    rows = [
        compare(row)
        for row in _read_csv(
            evaluations, {"cohort", "route", "previous", "prediction", "human_level"}
        )
    ]
    summaries = []
    for name in ("human_pilot150", "human_review50"):
        cohort = [r for r in rows if r["cohort"] == name]
        for route in ("all", "fallback", "wordfreq"):
            selected = [r for r in cohort if route == "all" or route == r["route"]]
            for label in ("all", "4", "5"):
                subset = [
                    r for r in selected if label == "all" or label == r["human_level"]
                ]
                summaries.append(
                    dict(
                        cohort=name, route=route, true_level=label, **summarize(subset)
                    )
                )
    output.mkdir(parents=True, exist_ok=False)
    _write_csv(output / "paired.csv", list(rows[0]), rows)
    _write_csv(output / "summary.csv", list(summaries[0]), summaries)
    if _sha256(evaluations) != expected:
        raise ValueError("Input changed during simulation")
    receipt = dict(
        evaluations_sha256=expected,
        script_sha256=_sha256(Path(__file__)),
        artifacts={
            name: _sha256(output / name) for name in ("paired.csv", "summary.csv")
        },
    )
    (output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.evaluations, args.output)
