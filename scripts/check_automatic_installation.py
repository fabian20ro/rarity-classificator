"""Rehearse automatic installation on owned OrioleDB; never accepts an application DSN."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full-inventory", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    protected = {}
    if args.full_inventory:
        contract_path = root / "docs/research/2026-11-06-promotion-package/contract.json"
        for local in (
            "automatic-installation-2026-11-07/capture.json",
            "automatic-installation-2026-11-07/verified/manifest.json",
        ):
            pinned = root.parent / local
            protected[str(pinned)] = sha(pinned)
        contract = json.loads(contract_path.read_text())
        protected[str(contract_path)] = sha(contract_path)
        for item in contract["inputs"].values():
            path = (contract_path.parent / item["path"]).resolve()
            assert sha(path) == item["sha256"]
            protected[str(path)] = item["sha256"]
    env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR") if k in os.environ}
    env.update(
        PYTHONPATH=str(root / "src"),
        RUN_AUTOMATIC_INSTALLATION_INTEGRATION="1",
        RUN_AUTOMATIC_INSTALLATION_FULL="1" if args.full_inventory else "0",
        HUMAN_PG_ENGINE="orioledb",
        HUMAN_PG_REPORT_PATH=str(out / "server.json"),
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/test_automatic_installation_postgres.py",
        "-q",
        "--tb=short",
        "--junitxml",
        str(out / "junit.xml"),
        "--basetemp",
        str(out / "test-artifacts"),
    ]
    result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
    (out / "output.txt").write_text(result.stdout + result.stderr)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    for path, expected in protected.items():
        assert sha(Path(path)) == expected, path
    cases = list(ElementTree.parse(out / "junit.xml").iter("testcase"))
    failed = sum(c.find("failure") is not None or c.find("error") is not None for c in cases)
    skipped = sum(c.find("skipped") is not None for c in cases)
    server = json.loads((out / "server.json").read_text())
    assert server["container_removed"] and server["volume_removed"]
    report = dict(
        server=server,
        tests=len(cases),
        passed=len(cases) - failed - skipped,
        failed=failed,
        skipped=skipped,
        exit_code=result.returncode,
        full_inventory=args.full_inventory,
        protected_sources_unchanged=len(protected),
        production_accessed=False,
        model_calls=0,
        limitations="Owned OrioleDB only. Small cases use synthetic revisions/epoch; the full fixture reconstructs the archived production identity, revisions and epoch. ACK loss is injected after real commit. No live deployment certification.",
    )
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    implementations = [
        "src/classificator/automatic_installation.py",
        "src/classificator/automatic_installation_checks.py",
        "src/classificator/human_installation.py",
        "src/classificator/automatic_promotion_flow.py",
        "src/classificator/automatic_promotion_postgres.py",
        "src/classificator/human_correction_postgres.py",
        "src/classificator/evaluation/promotion_audit.py",
        "tests/integration/test_automatic_installation_postgres.py",
        "tests/postgres_harness.py",
        "docs/sql/2026-11-06-automatic-promotion-receipts.sql",
        "scripts/check_automatic_installation.py",
    ]
    manifest = dict(
        inputs=protected,
        implementation={p: sha(root / p) for p in implementations},
        artifacts={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
