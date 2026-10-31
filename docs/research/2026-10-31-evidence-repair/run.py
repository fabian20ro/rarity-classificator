"""Pinned, paired native Codex sessions; no gold data enters model requests."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

from classificator.evaluation.chat_judge import PROMPT, SCHEMA
from classificator.evaluation.codex_judge import _answer, collect_codex_csv
from classificator.evaluation.dataset import _sha256
from classificator.models import BaseWordRow
from prepare import read, evidence


def run(out):
    protocol = json.loads((out / "protocol.json").read_text())
    for name, digest in protocol["frozen"].items():
        assert _sha256(Path(name)) == digest, name
    assert _sha256(Path(protocol["cli"]["path"])) == protocol["cli"]["sha256"]
    protected = json.loads((out / "protected-inputs.json").read_text())
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    config = json.loads((out / "config.json").read_text())
    env = {k: os.environ[k] for k in protocol["environment_allowlist"] if k in os.environ}
    options = []
    for key, value in config.items():
        encoded = (
            (
                "["
                + ",".join("{path=" + json.dumps(x["path"]) + ",enabled=false}" for x in value)
                + "]"
            )
            if isinstance(value, list)
            else json.dumps(value, ensure_ascii=False)
        )
        options += ["-c", key + "=" + encoded]
    inputs = {arm: evidence(out / arm / "inputs/evidence.csv") for arm in ("old", "corrected")}
    selections = read(out / "selection.csv")
    assert len(selections) * 2 <= protocol["max_lexical_calls"]
    total = 0
    try:
        for index, row in enumerate(selections):
            # Alternate arm order; each blocking process completes before the next starts.
            arms = ("old", "corrected") if index % 2 == 0 else ("corrected", "old")
            for arm in arms:
                item = BaseWordRow(int(row["word_id"]), row["word"], row["type"])
                request = dict(
                    model=protocol["model"],
                    reasoning_effort="low",
                    instructions=PROMPT,
                    input=dict(
                        word_id=item.word_id,
                        word=item.word,
                        inventory_type=item.type,
                        evidence=inputs[arm][row["word_id"]],
                    ),
                    response_schema=SCHEMA,
                )
                folder = out / arm / "processes"
                folder.mkdir(exist_ok=True)
                saved = folder / f"{item.word_id}.json"
                if saved.exists():
                    receipt = json.loads(saved.read_text())
                    assert receipt["request"] == request
                else:
                    cwd = Path(protocol["blind_root"]) / arm / str(item.word_id)
                    cwd.mkdir(parents=True, exist_ok=True)
                    assert not list(cwd.iterdir())
                    args = [
                        protocol["cli"]["path"],
                        "exec",
                        "--ignore-user-config",
                        "--skip-git-repo-check",
                        "--ephemeral",
                        "--json",
                        "--sandbox",
                        "read-only",
                        "--model",
                        protocol["model"],
                        "--cd",
                        str(cwd),
                        "--output-schema",
                        str(out / "response-schema.json"),
                        *options,
                        "-",
                    ]
                    start = time.time()
                    try:
                        result = subprocess.run(
                            args,
                            input=json.dumps(request["input"], ensure_ascii=False),
                            capture_output=True,
                            text=True,
                            cwd=cwd,
                            env=env,
                            timeout=180,
                        )
                        native = dict(
                            returncode=result.returncode, stdout=result.stdout, stderr=result.stderr
                        )
                    except subprocess.TimeoutExpired as exc:
                        native = dict(
                            returncode=124,
                            stdout=(exc.stdout or b"").decode()
                            if isinstance(exc.stdout, bytes)
                            else exc.stdout or "",
                            stderr=(exc.stderr or b"").decode()
                            if isinstance(exc.stderr, bytes)
                            else exc.stderr or "",
                        )
                    receipt = dict(
                        request=request,
                        result=native,
                        started=start,
                        finished=time.time(),
                        command=args,
                        cwd=str(cwd),
                        environment_keys=sorted(env),
                    )
                    temp = saved.with_suffix(".tmp")
                    temp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
                    temp.replace(saved)
                    assert not list(cwd.iterdir()), "Unexpected model filesystem side effect"
                # Fail closed on any runtime warning or tool activity; never repair/retry.
                _answer(receipt["result"], item)
                total += 1
                print(
                    f"Paired sequential session {total}/{len(selections) * 2}: {arm} {item.word_id}",
                    flush=True,
                )
        for arm in ("old", "corrected"):

            def replay(request):
                receipt = json.loads(
                    (out / arm / "processes" / f"{request['input']['word_id']}.json").read_text()
                )
                assert receipt["request"] == request
                return receipt["result"]

            with patch("psycopg.connect", side_effect=AssertionError("DB forbidden")):
                collect_codex_csv(
                    out / arm / "inputs/vocabulary.csv",
                    out / arm / "inputs/evidence.csv",
                    out / arm / "campaign",
                    executor=replay,
                    model=protocol["model"],
                    runtime=dict(
                        protocol_sha256=_sha256(out / "protocol.json"),
                        runner_sha256=_sha256(Path(__file__)),
                    ),
                )
    finally:
        for name, digest in protected.items():
            assert _sha256(Path(name)) == digest, name
        print(f"Protected {len(protected)} original files unchanged.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output.resolve())
