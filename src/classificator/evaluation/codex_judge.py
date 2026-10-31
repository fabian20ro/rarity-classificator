"""Native Codex judge receipts; configured model identity is not server attestation."""

import json
from pathlib import Path

from ..models import BaseWordRow
from ..scoring.base import Outcome
from . import chat_judge
from .campaign import run_campaign, _write_json
from .dataset import _sha256, _vocabulary


class ContaminatedSession(RuntimeError):
    """An unexpected event can expose additional information; stop the campaign."""


def _answer(result, item):
    if (
        not isinstance(result, dict)
        or type(result.get("returncode")) is not int
        or not isinstance(result.get("stdout"), str)
        or not isinstance(result.get("stderr"), str)
    ):
        raise ValueError("Invalid process receipt")
    if result["stderr"].strip():
        raise ContaminatedSession("Runtime stderr; isolation/configuration must be verified")
    events = []
    for line in result["stdout"].splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line, object_pairs_hook=chat_judge._unique)
        except ValueError as exc:
            raise ContaminatedSession("Unverifiable event stream") from exc
        if not isinstance(event, dict):
            raise ContaminatedSession("Invalid event object")
        kind = event.get("type")
        if kind in {"error", "turn.failed"}:
            events.append(event)
            continue
        if kind not in {
            "thread.started",
            "turn.started",
            "turn.completed",
            "item.started",
            "item.completed",
        }:
            raise ContaminatedSession("Unknown event")
        if kind.startswith("item."):
            value = event.get("item")
            if not isinstance(value, dict):
                raise ContaminatedSession("Invalid item object")
            if value.get("type") == "error":
                raise ContaminatedSession("Configuration/runtime warning")
            if value.get("type") not in {"agent_message", "reasoning"}:
                raise ContaminatedSession("Tool or unknown item")
        events.append(event)
    if result["returncode"] != 0 or any(e["type"] in {"error", "turn.failed"} for e in events):
        raise ValueError("Codex process/turn failed")
    messages = [
        e["item"]["text"]
        for e in events
        if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"
    ]
    types = [e["type"] for e in events]
    if (
        len(messages) != 1
        or types[:2] != ["thread.started", "turn.started"]
        or types[-1:] != ["turn.completed"]
        or any(types.count(t) != 1 for t in ["thread.started", "turn.started", "turn.completed"])
        or not isinstance(events[0].get("thread_id"), str)
        or not events[0]["thread_id"].strip()
    ):
        raise ValueError("Require one complete final answer")
    answer = json.loads(messages[0], object_pairs_hook=chat_judge._unique)
    if (
        not isinstance(answer, dict)
        or set(answer) != set(chat_judge.SCHEMA["required"])
        or type(answer["word_id"]) is not int
        or answer["word_id"] != item.word_id
        or answer["word"] != item.word
        or type(answer["level"]) is not int
        or not 1 <= answer["level"] <= 5
        or not isinstance(answer["note"], str)
        or not answer["note"].strip()
        or len(answer["note"]) > 400
    ):
        raise ValueError("Invalid judgment identity/schema/level")
    return answer


class CodexJudge:
    def __init__(self, model, evidence, executor, output_dir):
        self.model, self.evidence, self.executor = model, evidence, executor
        self.output_dir = output_dir

    def score_batch(self, items):
        outcomes = []
        for item in items:
            request = dict(
                model=self.model,
                reasoning_effort="low",
                instructions=chat_judge.PROMPT,
                input=dict(
                    word_id=item.word_id,
                    word=item.word,
                    inventory_type=item.type,
                    evidence=self.evidence[item.word_id],
                ),
                response_schema=chat_judge.SCHEMA,
            )
            result = self.executor(request)
            raw = json.dumps(result, ensure_ascii=False)
            try:
                answer = _answer(result, item)
                outcomes.append(
                    Outcome(item.word_id, answer["level"], request=request, response=raw)
                )
            except ContaminatedSession as exc:
                directory = self.output_dir / "quarantine"
                directory.mkdir(exist_ok=True)
                _write_json(
                    directory / f"{item.word_id}.json",
                    dict(request=request, response=result, reason=str(exc)),
                )
                raise RuntimeError("Campaign quarantined: " + str(exc)) from exc
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                outcomes.append(
                    Outcome(
                        item.word_id,
                        None,
                        status="failed",
                        error=str(exc),
                        request=request,
                        response=raw,
                    )
                )
        return outcomes


def collect_codex_csv(vocabulary_csv, evidence_csv, output_dir, *, executor, model, runtime):
    """Collect isolated one-form sessions; executor owns process isolation/raw logs.

    The configured model/effort and generic Codex wrapper are explicit provenance.
    No HTTP response, served-model identity, probability or confidence is invented.
    """
    if (output_dir / "quarantine").exists():
        raise RuntimeError("Campaign quarantined; inspect receipts and use a new campaign")
    items = [
        BaseWordRow(int(r["word_id"]), r["word"], r["type"]) for r in _vocabulary(vocabulary_csv)
    ]
    evidence = chat_judge._evidence(evidence_csv, items)
    config = dict(
        transport="codex-exec-native",
        configured_model=model,
        reasoning_effort="low",
        runtime=runtime,
        evidence_sha256=_sha256(evidence_csv),
        vocabulary_sha256=_sha256(vocabulary_csv),
        collector_sha256=_sha256(Path(__file__)),
        shared_contract_sha256=_sha256(Path(chat_judge.__file__)),
    )
    return run_campaign(
        items, CodexJudge(model, evidence, executor, output_dir), output_dir, config=config
    )
