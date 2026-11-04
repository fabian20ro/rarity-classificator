"""Add all previously curated exact-form contexts; keep provenance out of model input."""

import argparse
import json
from pathlib import Path

from classificator.evaluation.judge_evidence import merge_judge_evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("evidence", "form-contract-dir", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--projection", type=Path, help="Audited complete lexical projection CSV")
    args = parser.parse_args()
    print(
        json.dumps(
            merge_judge_evidence(
                args.evidence,
                args.form_contract_dir,
                args.output_dir,
                projection_csv=args.projection,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
