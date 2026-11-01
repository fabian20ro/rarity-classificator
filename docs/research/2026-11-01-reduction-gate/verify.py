"""Byte-identical gate replay and independent reference arithmetic; no external I/O."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from classificator.evaluation.dataset import _read_csv, _sha256
from classificator.evaluation.reduction_gate import export_reduction_gate

parser = argparse.ArgumentParser()
parser.add_argument("--base", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
base, out = args.base.resolve(), args.output.resolve()
report = json.loads((out / "report.json").read_text())
protocol = json.loads((out / "protocol.json").read_text())
protected = json.loads((out / "protected-inputs.json").read_text())
for name, digest in {
    **protected,
    **protocol["frozen"],
    **protocol["source_inputs"],
    **report["reference_sha256"],
}.items():
    assert _sha256(Path(name)) == digest, name
manifest = json.loads((out / "analysis-manifest.json").read_text())
for name, digest in manifest["artifacts"].items():
    assert _sha256(out / name) == digest, name
identical = 0
methods = protocol["methods"]
corpus_extra = 0
co_supported = 0
eligible = 0
with (
    patch("subprocess.run", side_effect=AssertionError("LLM/process forbidden")),
    patch("subprocess.Popen", side_effect=AssertionError("LLM/process forbidden")),
    patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
    patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
    patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
    TemporaryDirectory(dir=out) as temp,
):
    for cohort in report["cohorts"]:
        inputs = out / cohort / "inputs"
        target = Path(temp) / cohort
        export_reduction_gate(
            inputs / "baseline.csv",
            inputs / "evidence.csv",
            inputs / "gpt.csv",
            base / "fineweb-2026-10-26/source",
            base / "corola-2026-10-28/source",
            target,
        )
        for path in target.iterdir():
            assert path.read_bytes() == (out / cohort / "gate" / path.name).read_bytes()
            identical += 1
        rows = _read_csv(out / cohort / "comparison.csv", set())
        gold_path = base / (
            "gpt-judge-2026-10-31/inputs/reference.csv"
            if cohort == "pilot150"
            else "review50-2026-10-31/review-responses.csv"
        )
        refs = {r["word_id"]: r for r in _read_csv(gold_path, set())}
        assert set(refs) == {r["word_id"] for r in rows}
        for r in rows:
            assert (r["word"], r["human_level"]) == (
                refs[r["word_id"]]["word"],
                refs[r["word_id"]]["working_level"],
            )
            corpus_extra += r["candidate_level"] != r["lexical_only_level"]
            eligible += r["large_reduction"] == "True"
            co_supported += r["large_reduction"] == "True" and r["corola_supported"] == "True"
        for name, metric in report["cohorts"][cohort]["strata"].items():
            selected = [
                r
                for r in rows
                if name == "all"
                or name == "large_reductions"
                and r["large_reduction"] == "True"
                or name == "true4"
                and r["human_level"] == "4"
                or name == "true5"
                and r["human_level"] == "5"
                or name == "true45"
                and r["human_level"] in ("4", "5")
            ]
            for method in methods:
                errors = [abs(int(r[method]) - int(r["human_level"])) for r in selected]
                assert metric[method]["n"] == len(errors)
                assert metric[method]["severe"] == len([d for d in errors if d > 1])
                assert metric[method]["excess_error_total"] == sum(d - 1 for d in errors if d > 1)
                assert metric[method]["within_one"] == len([d for d in errors if d <= 1])
verification = dict(
    protected_files_unchanged=len(protected),
    replay="PASS",
    byte_identical_artifacts=identical,
    independent_reference_and_metric_checks="PASS",
    corpus_changes_beyond_lexical_gate=corpus_extra,
    large_reductions=eligible,
    corola_supported_large_reductions=co_supported,
    model_calls=0,
    classifier_db_writes=0,
    new_downloads=0,
    full_coverage={"pilot150": 150, "review50": 50},
)
(out / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
print(json.dumps(verification, indent=2))
