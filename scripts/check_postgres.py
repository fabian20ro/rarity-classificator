"""Opt-in disposable PostgreSQL integration; never consumes an application DSN."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", choices=("heap", "orioledb"), default="heap")
    parser.add_argument(
        "--full-inventory",
        action="store_true",
        help="Also use the existing local 165-correction package",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    protected = {}
    if args.full_inventory:
        policy = json.loads(
            (root / "docs/research/2026-11-03-human-acceptance/policy.json").read_text()
        )
        previous = (
            Path(policy["sources"]["candidate"]["path"]).parent.parent
            / "human-production-preflight-2026-11-03"
        )
        protected = json.loads((previous / "protected-inputs.json").read_text())
        protected.update({str(p): digest(p) for p in previous.rglob("*") if p.is_file()})
        for path, expected in protected.items():
            assert digest(Path(path)) == expected, path
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/test_human_flow_postgres.py",
        "-q",
        "--tb=short",
        "--junitxml",
        str(out / "junit.xml"),
        "--basetemp",
        str(out / "test-artifacts"),
    ]
    env = dict(
        os.environ,
        RUN_HUMAN_POSTGRES_INTEGRATION="1",
        RUN_HUMAN_POSTGRES_FULL_INVENTORY="1" if args.full_inventory else "0",
        HUMAN_PG_REPORT_PATH=str(out / "server.json"),
        HUMAN_PG_ENGINE=args.engine,
    )
    result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
    (out / "test-output.txt").write_text(result.stdout + result.stderr)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    suites = ElementTree.parse(out / "junit.xml")
    cases = list(suites.iter("testcase"))
    failed = sum(
        case.find("failure") is not None or case.find("error") is not None for case in cases
    )
    skipped = sum(case.find("skipped") is not None for case in cases)
    for path, expected in protected.items():
        assert digest(Path(path)) == expected, path
    server = json.loads((out / "server.json").read_text())
    report = dict(
        server=server,
        tests=len(cases),
        failed=failed,
        skipped=skipped,
        passed=len(cases) - failed - skipped,
        exit_code=result.returncode,
        full_inventory=args.full_inventory,
        protected_files_unchanged=len(protected),
        project_database_accessed=False,
        model_calls=0,
        caveat="Owned disposable database only. Fixture roles/triggers, not deployment certification. Post-commit ACK loss is injected after real commit; disconnect/restart are real. Trusted schema/backup administrators must preserve revision epochs and sequence history.",
    )
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "protected-inputs.json").write_text(json.dumps(protected, indent=2) + "\n")
    files = [
        "scripts/check_postgres.py",
        "tests/postgres_harness.py",
        "tests/integration/test_human_flow_postgres.py",
        "src/classificator/human_correction_flow.py",
        "src/classificator/human_correction_postgres.py",
        "docs/sql/2026-11-03-human-correction-receipts.sql",
        "docs/sql/2026-11-03-human-row-revisions.sql",
    ]
    manifest = dict(
        implementation={str(root / f): digest(root / f) for f in files},
        artifacts={str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()},
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    assert server["container_removed"] and server["volume_removed"]
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
