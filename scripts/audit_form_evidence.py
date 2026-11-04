"""Audit existing lexical/form CSV exports without models or database access."""

import argparse
import json
from pathlib import Path

from classificator.evaluation.form_evidence_audit import audit_form_evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("forms", "inventory", "lexical-dir", "form-contract-dir", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            audit_form_evidence(
                args.forms,
                args.inventory,
                args.lexical_dir,
                args.form_contract_dir,
                args.output_dir,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
