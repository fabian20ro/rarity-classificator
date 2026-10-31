"""Sequential evidence CSV -> chat HTTP -> resumable predictions, without gold."""

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

from classificator.evaluation.chat_judge import collect_chat_csv
from tests.test_exact_form import write_csv


def read(path):
    return list(csv.DictReader(path.open()))


def response(word_id=1, word="ata", level=5, **change):
    body = dict(
        model="test-model",
        choices=[
            dict(
                index=0,
                finish_reason="stop",
                message=dict(
                    role="assistant",
                    content=json.dumps(
                        dict(word_id=word_id, word=word, level=level, note="Sens lexical exact.")
                    ),
                ),
            )
        ],
    )
    body.update(change)
    result = Mock()
    result.text = json.dumps(body)
    return result


class ChatJudgeTests(unittest.TestCase):
    def inputs(self, root):
        vocabulary = write_csv(
            root / "vocabulary.csv",
            [dict(word_id=1, word="ata", type="N"), dict(word_id=2, word="ață", type="N")],
        )
        evidence = write_csv(
            root / "evidence.csv",
            [
                dict(
                    word_id=i,
                    word=w,
                    evidence_json=json.dumps(
                        dict(
                            coverage="source_bounded_not_exhaustive",
                            valid_pos=["substantiv"],
                            senses=[],
                        )
                    ),
                )
                for i, w in [(1, "ata"), (2, "ață")]
            ],
        )
        return vocabulary, evidence

    def test_collects_both_exact_forms_sequentially_and_resumes_without_fake_confidence(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            http = Mock()
            sent = []

            def post(url, *, json, timeout):
                state = __import__("json").loads(json["messages"][1]["content"])
                sent.append(state["word"])
                self.assertEqual(len(json["messages"]), 2)
                self.assertFalse(json["stream"])
                return response(state["word_id"], state["word"], 5 if state["word"] == "ata" else 1)

            http.post.side_effect = post
            args = self.inputs(root)
            path = collect_chat_csv(
                *args,
                root / "out",
                model="test-model",
                endpoint="http://localhost/v1/chat/completions",
                http=http,
            )
            rows = read(path)
            self.assertEqual(sent, ["ata", "ață"])
            self.assertEqual([r["rarity_level"] for r in rows], ["5", "1"])
            self.assertEqual([r["confidence"] for r in rows], ["", ""])
            self.assertTrue(all(r["p_L1"] == "" for r in rows))
            collect_chat_csv(
                *args,
                root / "out",
                model="test-model",
                endpoint="http://localhost/v1/chat/completions",
                http=http,
            )
            self.assertEqual(sent, ["ata", "ață"])
            self.assertEqual(read(root / "out/run.csv"), [])

    def test_invalid_responses_are_failures_with_raw_evidence_never_repaired(self):
        variants = [
            dict(word_id=99, word="ata", level=5, note="x"),
            dict(word_id=1, word="ață", level=5, note="x"),
            dict(word_id=1, word="ata", level=True, note="x"),
            dict(word_id=1, word="ata", level=5.0, note="x"),
            dict(word_id=1, word="ata", level=6, note="x"),
            dict(word_id=1, word="ata", level=5, note="x", confidence=0.9),
            '{"word_id":1,"word":"ata","level":1,"level":5,"note":"x"}',
            '```json\n{"level":5}\n```',
        ]
        for answer in variants:
            with self.subTest(answer=answer), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                http = Mock()
                body = json.loads(response().text)
                body["choices"][0]["message"]["content"] = (
                    json.dumps(answer) if isinstance(answer, dict) else answer
                )
                raw = json.dumps(body)
                http.post.return_value = Mock(text=raw)
                path = collect_chat_csv(
                    *args,
                    root / "out",
                    model="test-model",
                    endpoint="http://localhost/v1/chat/completions",
                    http=http,
                )
                self.assertTrue(
                    all(r["status"] == "failed" and r["rarity_level"] == "" for r in read(path))
                )
                self.assertEqual(
                    json.loads((root / "out/records/1.json").read_text())["response"], raw
                )

    def test_rejects_truncation_refusal_tools_multiple_choices_and_wrong_served_model(self):
        changes = [
            ("finish_reason", "length"),
            ("refusal", "cannot"),
            ("tool_calls", [{}]),
            ("role", "user"),
            ("choices", 2),
            ("model", "other"),
        ]
        for key, value in changes:
            with self.subTest(key=key), TemporaryDirectory() as temp:
                root = Path(temp)
                http = Mock()
                body = json.loads(response().text)
                if key == "choices":
                    body["choices"] *= value
                elif key == "model":
                    body[key] = value
                elif key == "finish_reason":
                    body["choices"][0][key] = value
                else:
                    body["choices"][0]["message"][key] = value
                http.post.return_value = Mock(text=json.dumps(body))
                path = collect_chat_csv(
                    *self.inputs(root),
                    root / "out",
                    model="test-model",
                    endpoint="http://localhost/v1/chat/completions",
                    http=http,
                )
                self.assertTrue(all(r["status"] == "failed" for r in read(path)))

    def test_rejects_label_leakage_incomplete_identity_and_transport_overrides_before_http(self):
        for defect in (
            "gold",
            "nested_gold",
            "wrong_word",
            "missing",
            "duplicate",
            "messages",
            "stream",
            "n",
            "api_key",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                http = Mock()
                rows = read(args[1])
                options = {}
                if defect in ("messages", "stream", "n", "api_key"):
                    options[defect] = "forbidden"
                elif defect == "missing":
                    rows = rows[:1]
                elif defect == "duplicate":
                    rows.append(rows[0])
                elif defect == "wrong_word":
                    rows[0]["word"] = "ață"
                else:
                    value = json.loads(rows[0]["evidence_json"])
                    if defect == "gold":
                        value["human_level"] = 5
                    else:
                        value["senses"] = [
                            dict(
                                pos="N",
                                definition="Valid.",
                                number_restriction="",
                                grammar=[],
                                context=[],
                                context_incomplete=False,
                                human_level=5,
                            )
                        ]
                    rows[0]["evidence_json"] = json.dumps(value)
                write_csv(args[1], rows)
                with self.assertRaises(ValueError):
                    collect_chat_csv(
                        *args,
                        root / "out",
                        model="test-model",
                        endpoint="http://localhost/v1/chat/completions",
                        http=http,
                        options=options,
                    )
                http.post.assert_not_called()

    def test_resume_refuses_changed_provider_options_or_evidence_before_http(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            http = Mock()
            http.post.side_effect = [response(), response(2, "ață", 1)]
            collect_chat_csv(
                *args,
                root / "out",
                model="test-model",
                endpoint="http://localhost/v1/chat/completions",
                http=http,
            )
            http.reset_mock()
            for change in (
                {"model": "gpt-future"},
                {"options": {"reasoning_effort": "low"}},
                {"endpoint": "https://example.test/v1/chat/completions"},
            ):
                kwargs = dict(
                    model="test-model", endpoint="http://localhost/v1/chat/completions", http=http
                )
                kwargs.update(change)
                with self.assertRaisesRegex(ValueError, "changed"):
                    collect_chat_csv(*args, root / "out", **kwargs)
            rows = read(args[1])
            e = json.loads(rows[0]["evidence_json"])
            e["valid_pos"].append("adjectiv")
            rows[0]["evidence_json"] = json.dumps(e)
            write_csv(args[1], rows)
            with self.assertRaisesRegex(ValueError, "changed"):
                collect_chat_csv(
                    *args,
                    root / "out",
                    model="test-model",
                    endpoint="http://localhost/v1/chat/completions",
                    http=http,
                )
            http.post.assert_not_called()

    def test_memory_gate_interrupt_keeps_completed_checkpoint_for_resume(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            http = Mock()
            http.post.return_value = response()

            def gate(wid):
                if wid == 2:
                    raise RuntimeError("RAM guard")

            with self.assertRaisesRegex(RuntimeError, "RAM"):
                collect_chat_csv(
                    *args,
                    root / "out",
                    model="test-model",
                    endpoint="http://localhost/v1/chat/completions",
                    http=http,
                    before_request=gate,
                )
            self.assertEqual([r["word_id"] for r in read(root / "out/predictions.csv")], ["1"])
            http.post.return_value = response(2, "ață", 1)
            collect_chat_csv(
                *args,
                root / "out",
                model="test-model",
                endpoint="http://localhost/v1/chat/completions",
                http=http,
            )
            self.assertEqual(http.post.call_count, 2)

    def test_malformed_message_is_recorded_as_failure_not_an_uncheckpointed_crash(self):
        for message in (None, [], "not a message"):
            with self.subTest(message=message), TemporaryDirectory() as temp:
                root = Path(temp)
                http = Mock()
                body = json.loads(response().text)
                body["choices"][0]["message"] = message
                http.post.return_value = Mock(text=json.dumps(body))
                path = collect_chat_csv(
                    *self.inputs(root),
                    root / "out",
                    model="test-model",
                    endpoint="http://localhost/v1/chat/completions",
                    http=http,
                )
                self.assertTrue(all(r["status"] == "failed" for r in read(path)))

    def test_caller_mutation_cannot_change_pinned_provider_options(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            http = Mock()
            http.post.side_effect = [response(), response(2, "ață", 1)]
            options = {"temperature": 0}

            def guard(wid):
                options["temperature"] = 1

            collect_chat_csv(
                *self.inputs(root),
                root / "out",
                model="test-model",
                endpoint="http://localhost/v1/chat/completions",
                http=http,
                options=options,
                before_request=guard,
            )
            self.assertEqual(
                [call.kwargs["json"]["temperature"] for call in http.post.call_args_list], [0, 0]
            )
