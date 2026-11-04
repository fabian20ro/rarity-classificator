"""Public CSV collection with isolated native Codex execution receipts."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.codex_judge import collect_codex_csv
from tests.test_exact_form import write_csv
from tests.test_local_evidence import read


def native(answer, session="s1"):
    return dict(
        returncode=0,
        stderr="",
        stdout="\n".join(
            json.dumps(e)
            for e in [
                dict(type="thread.started", thread_id=session),
                dict(type="turn.started"),
                dict(
                    type="item.completed", item=dict(type="agent_message", text=json.dumps(answer))
                ),
                dict(type="turn.completed", usage=dict(input_tokens=100, output_tokens=20)),
            ]
        ),
    )


def inputs(root):
    rows = [dict(word_id=1, word="ata", type="N"), dict(word_id=2, word="ață", type="N")]
    vocabulary = write_csv(root / "v.csv", rows)
    evidence = write_csv(
        root / "e.csv",
        [
            dict(
                word_id=r["word_id"],
                word=r["word"],
                evidence_json=json.dumps(
                    dict(
                        coverage="source_bounded_not_exhaustive",
                        valid_pos=["substantiv feminin"],
                        senses=[],
                    )
                ),
            )
            for r in rows
        ],
    )
    return vocabulary, evidence


class CodexJudgeTests(unittest.TestCase):
    def test_collects_sequential_native_receipts_without_gold_and_resumes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            v, e = inputs(root)
            seen = []

            def execute(request):
                state = request["input"]
                seen.append(state["word_id"])
                self.assertEqual(set(state), {"word_id", "word", "inventory_type", "evidence"})
                self.assertEqual(request["model"], "gpt-6.1-sol")
                self.assertEqual(request["reasoning_effort"], "low")
                return native(
                    dict(word_id=state["word_id"], word=state["word"], level=4, note="Sens rar."),
                    str(state["word_id"]),
                )

            collect_codex_csv(
                v,
                e,
                root / "out",
                executor=execute,
                model="gpt-6.1-sol",
                runtime={"probe": "verified"},
            )
            self.assertEqual(seen, [1, 2])
            self.assertEqual(
                [r["rarity_level"] for r in read(root / "out/predictions.csv")], ["4", "4"]
            )
            record = json.loads((root / "out/records/1.json").read_text())
            self.assertIsNone(record["confidence"])
            self.assertEqual(record["probabilities"], [])
            self.assertIn("thread.started", json.loads(record["response"])["stdout"])
            collect_codex_csv(
                v,
                e,
                root / "out",
                executor=execute,
                model="gpt-6.1-sol",
                runtime={"probe": "verified"},
            )
            self.assertEqual(seen, [1, 2])

    def test_tool_or_unknown_events_quarantine_and_stop_before_next_form(self):
        for bad in [
            dict(
                type="item.started", item=dict(type="command_execution", command="cat labels.csv")
            ),
            dict(type="future.unknown"),
        ]:
            with self.subTest(bad=bad), TemporaryDirectory() as temp:
                root = Path(temp)
                v, e = inputs(root)
                seen = []

                def execute(request):
                    seen.append(request["input"]["word_id"])
                    result = native(dict(word_id=1, word="ata", level=4, note="Rar."))
                    events = result["stdout"].splitlines()
                    events.insert(2, json.dumps(bad))
                    result["stdout"] = "\n".join(events)
                    return result

                with self.assertRaisesRegex(RuntimeError, "quarantined"):
                    collect_codex_csv(
                        v, e, root / "out", executor=execute, model="gpt-6.1-sol", runtime={}
                    )
                self.assertEqual(seen, [1])
                self.assertTrue((root / "out/quarantine/1.json").exists())
                self.assertEqual(read(root / "out/predictions.csv"), [])
                with self.assertRaisesRegex(RuntimeError, "quarantined"):
                    collect_codex_csv(
                        v, e, root / "out", executor=execute, model="gpt-6.1-sol", runtime={}
                    )
                self.assertEqual(seen, [1])

    def test_invalid_native_results_stay_failed_without_silent_repair(self):
        good = dict(word_id=1, word="ata", level=4, note="Sens rar.")
        variants = []
        for field, value in [
            ("word_id", 2),
            ("word", "ață"),
            ("level", True),
            ("level", 4.0),
            ("level", 6),
            ("note", ""),
            ("note", "x" * 401),
            ("human_level", 5),
        ]:
            variants.append(native(dict(good, **{field: value})))
        missing = native(good)
        missing["stdout"] = "\n".join(missing["stdout"].splitlines()[1:])
        variants.append(missing)
        multiple = native(good)
        multiple["stdout"] = multiple["stdout"] + "\n" + json.dumps(dict(type="turn.completed"))
        variants.append(multiple)
        broken = native(good)
        broken["stdout"] = None
        variants.append(broken)
        false_code = native(good)
        false_code["returncode"] = False
        variants.append(false_code)
        variants.append(dict(returncode=1, stdout="", stderr=""))
        for result in variants:
            with self.subTest(result=result), TemporaryDirectory() as temp:
                root = Path(temp)
                v, e = inputs(root)

                def execute(request):
                    return (
                        result
                        if request["input"]["word_id"] == 1
                        else native(dict(word_id=2, word="ață", level=1, note="Comun."), "s2")
                    )

                collect_codex_csv(
                    v, e, root / "out", executor=execute, model="gpt-6.1-sol", runtime={}
                )
                rows = read(root / "out/predictions.csv")
                self.assertEqual(rows[0]["status"], "failed")
                self.assertEqual(rows[0]["rarity_level"], "")
                self.assertEqual(rows[1]["rarity_level"], "1")

    def test_resume_rejects_model_runtime_and_evidence_drift(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            v, e = inputs(root)
            calls = []

            def execute(request):
                state = request["input"]
                calls.append(state["word_id"])
                return native(
                    dict(word_id=state["word_id"], word=state["word"], level=3, note="Moderat."),
                    str(state["word_id"]),
                )

            collect_codex_csv(
                v, e, root / "out", executor=execute, model="gpt-6.1-sol", runtime={"version": 1}
            )
            for model, runtime in [("different", {"version": 1}), ("gpt-6.1-sol", {"version": 2})]:
                with self.assertRaises(ValueError):
                    collect_codex_csv(
                        v, e, root / "out", executor=execute, model=model, runtime=runtime
                    )
            e.write_text(e.read_text() + "\n")
            with self.assertRaises(ValueError):
                collect_codex_csv(
                    v,
                    e,
                    root / "out",
                    executor=execute,
                    model="gpt-6.1-sol",
                    runtime={"version": 1},
                )
            self.assertEqual(calls, [1, 2])

    def test_tool_events_are_fatal_even_when_process_fails_or_later_log_is_broken(self):
        for tail in ["", "not-json"]:
            with self.subTest(tail=tail), TemporaryDirectory() as temp:
                root = Path(temp)
                v, e = inputs(root)

                def execute(request):
                    return dict(
                        returncode=1,
                        stderr="",
                        stdout=json.dumps(
                            dict(type="item.started", item=dict(type="mcp_tool_call"))
                        )
                        + "\n"
                        + tail,
                    )

                with self.assertRaisesRegex(RuntimeError, "quarantined"):
                    collect_codex_csv(
                        v, e, root / "out", executor=execute, model="gpt-6.1-sol", runtime={}
                    )
                self.assertTrue((root / "out/quarantine/1.json").exists())

    def test_runtime_warning_or_malformed_item_quarantines_before_next_form(self):
        for mutation in ["warning", "malformed_then_tool"]:
            with self.subTest(mutation=mutation), TemporaryDirectory() as temp:
                root = Path(temp)
                v, e = inputs(root)
                calls = []

                def execute(request):
                    calls.append(request["input"]["word_id"])
                    result = native(dict(word_id=1, word="ata", level=4, note="Rar."))
                    if mutation == "warning":
                        result["stderr"] = "WARN isolation option ignored"
                    else:
                        events = result["stdout"].splitlines()
                        events[2:2] = [
                            json.dumps(dict(type="item.started", item=None)),
                            json.dumps(
                                dict(type="item.started", item=dict(type="command_execution"))
                            ),
                        ]
                        result["stdout"] = "\n".join(events)
                    return result

                with self.assertRaisesRegex(RuntimeError, "quarantined"):
                    collect_codex_csv(
                        v, e, root / "out", executor=execute, model="gpt-6.1-sol", runtime={}
                    )
                self.assertEqual(calls, [1])
