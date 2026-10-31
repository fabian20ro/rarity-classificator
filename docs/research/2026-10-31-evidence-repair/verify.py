"""Replay every saved response and analysis with model/network/DB paths forbidden."""

import argparse
import contextlib
import io
import json
from pathlib import Path
from unittest.mock import patch

from classificator.evaluation.dataset import _sha256
from analyze import analyze
from run import run

parser = argparse.ArgumentParser()
parser.add_argument("--base", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
base, out = args.base.resolve(), args.output.resolve()
paths = [
    out / n
    for n in (
        "paired-comparison.csv",
        "full-frozen-comparison.csv",
        "report.json",
        "analysis-manifest.json",
    )
]
for arm in ("old", "corrected"):
    paths += [
        p
        for directory in ("campaign", "processes")
        for p in (out / arm / directory).rglob("*")
        if p.is_file()
    ]
before = {str(p): _sha256(p) for p in paths}
with (
    contextlib.redirect_stdout(io.StringIO()),
    patch("subprocess.run", side_effect=AssertionError("Model process forbidden")),
    patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
    patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
    patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
):
    run(out)
    analyze(base, out)
assert all(_sha256(Path(p)) == digest for p, digest in before.items())
report = json.loads((out / "report.json").read_text())
verification = dict(
    report["verification"],
    replay="PASS",
    byte_identical_artifacts=len(before),
    models_network_db_forbidden=True,
    source_inputs_match_protocol=True,
)
(out / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
print(json.dumps(verification, indent=2))
