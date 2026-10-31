"""Project a verified lexical audit into blinded judge evidence CSVs."""

import argparse
from pathlib import Path

from classificator.evaluation.audit_judge_evidence import export_audit_judge_evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forms", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(export_audit_judge_evidence(args.forms, args.vocabulary, args.audit, args.output))


if __name__ == "__main__":
    main()
