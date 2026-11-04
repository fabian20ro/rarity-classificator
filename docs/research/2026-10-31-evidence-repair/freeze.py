"""Freeze one bounded experiment before any new predictions. No labels read."""

import argparse
import datetime
import json
import shutil
from pathlib import Path
from classificator.evaluation.chat_judge import PROMPT, SCHEMA
from classificator.evaluation.dataset import _sha256

parser = argparse.ArgumentParser()
parser.add_argument("--base", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
base, out = args.base.resolve(), args.output.resolve()
assert not (out / "protocol.json").exists()
previous = base / "1000-judges-2026-10-31/gpt"
old = json.loads((previous / "protocol.json").read_text())
assert (previous / "prompt.txt").read_text() == PROMPT + "\n"
assert json.loads((previous / "response-schema.json").read_text()) == SCHEMA
for name in ("prompt.txt", "response-schema.json"):
    shutil.copyfile(previous / name, out / name)
shutil.copyfile(previous / "preflight/catalog.json", out / "catalog.json")
config = json.loads((previous / "config.json").read_text())
config.update(
    model_instructions_file=str(out / "prompt.txt"),
    sqlite_home=str(out / "runtime-state"),
    log_dir=str(out / "runtime-logs"),
    model_catalog_json=str(out / "catalog.json"),
)
(out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
code = Path(__file__).resolve().parents[3]
paths = [
    *out.glob("*/inputs/*.csv"),
    out / "selection.csv",
    out / "evidence-diff.csv",
    out / "protected-inputs.json",
    out / "config.json",
    out / "prompt.txt",
    out / "response-schema.json",
    out / "catalog.json",
    *Path(__file__).parent.glob("*.py"),
    *(code / "src/classificator/evaluation").glob("*.py"),
]
protocol = dict(
    created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    design="Existing development references only. 5 documented sentinels, 15 deterministic content changes, 10 identical-input repeat controls; 30 forms, old/corrected fresh paired sessions. Alternate arm order. Cohorts reported separately. Same prompt/settings. No tuning after results.",
    selection="Exact selection.csv frozen before inference; SHA rank evidence-repair-v1:ID, no labels read. Known sentinels are diagnostic, not unbiased sampling.",
    max_lexical_calls=60,
    model=old["model"],
    reasoning_effort="low",
    cli=old["cli"],
    environment_allowlist=old["environment_allowlist"],
    blind_root="/private/tmp/wrc-evidence-repair-2026-10-31",
    transport="Native Codex ephemeral sessions, configured identity only. Generic managed instructions/tools remain as in original pilot; tool/unknown/runtime-warning events stop collection. No project cwd or gold in requests. One blocking subprocess at a time, no application retries.",
    metrics="Paired severe abs(error)>=2, excess max(abs(error)-1,0), MAE, true4 and true5 separately; 150 and risk-selected50 never pooled. Controls report repeat variation. Compare historical full-cohort baseline/GPT plus fixed context gate: GPT iff old senses nonempty, otherwise baseline. Gate post-hoc development only.",
    promotion="No production promotion from this small reused sample, even if improved. A candidate merits a larger frozen paired test only if severe and excess do not increase in either cohort nor true4/5. Otherwise retain operational baseline; no human round or DB update.",
    failures="Persist raw receipts, stop on invalid session; do not silently drop, retry or replace selected forms.",
    frozen={str(p): _sha256(p) for p in paths},
)
(out / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
print("Frozen " + str(out / "protocol.json"))
