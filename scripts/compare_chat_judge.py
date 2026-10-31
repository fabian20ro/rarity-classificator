"""Compare any chat-judge campaign with frozen human references and baseline."""

import argparse
import json
from pathlib import Path

from classificator.evaluation.judge_comparison import compare_judge_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("predictions", "reference", "baseline", "evidence", "folds", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--review-budget", type=int, default=8)
    args = parser.parse_args()
    result = compare_judge_csv(
        args.predictions,
        args.reference,
        args.baseline,
        args.evidence,
        args.folds,
        args.output_dir,
        review_budget=args.review_budget,
    )
    print(json.dumps({"coverage": result["coverage"], "promotion": result["promotion"]}, indent=2))


if __name__ == "__main__":
    main()
