"""Export frozen label-free Qwen routes and at most50 human review candidates."""

import argparse
from pathlib import Path

from classificator.evaluation.risk_queue import export_risk_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["baseline", "evidence", "gpt", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--qwen", type=Path)
    parser.add_argument("--review-budget", type=int, default=50)
    args = parser.parse_args()
    print(
        export_risk_csv(
            args.baseline,
            args.evidence,
            args.gpt,
            args.output,
            qwen_csv=args.qwen,
            review_budget=args.review_budget,
        )
    )


if __name__ == "__main__":
    main()
