#!/usr/bin/env python3
"""Offline CSV-only fixed ordinal comparison; no network, subprocess or DB calls."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path, help="Frozen v3 features.csv + inputs.json directory")
    parser.add_argument("references", type=Path, help="Unchanged human references CSV")
    parser.add_argument("comparisons", type=Path, help="Frozen class-bias comparison directory")
    parser.add_argument("output", type=Path, help="New output directory (never overwritten)")
    args = parser.parse_args()

    def deny(*_args, **_kwargs):
        raise RuntimeError("Ordinal experiment is offline: network, subprocess and DB forbidden")

    def guard(event, _args):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"}:
            deny()

    sys.addaudithook(guard)
    import psycopg

    psycopg.connect = deny
    from classificator.evaluation.d1_ordinal import evaluate_d1_ordinal

    report = evaluate_d1_ordinal(args.inputs, args.references, args.comparisons, args.output)
    for cohort, methods in report["cohorts"].items():
        print(cohort, {name: values["all"]["severe"] for name, values in methods.items()})
    print("Baseline gate:", report["decisions"]["baseline_gate"]["passes"])
    print("Artifacts:", args.output.resolve())


if __name__ == "__main__":
    main()
