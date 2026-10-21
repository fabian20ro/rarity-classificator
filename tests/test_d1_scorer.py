import json
import unittest
from unittest.mock import Mock

from classificator.models import BaseWordRow
from classificator.scoring.d1 import D1Scorer


def response(body, status=200):
    result = Mock(status_code=status, text=json.dumps(body))
    result.raise_for_status.return_value = None
    return result


def models():
    return {
        "models": [
            {
                "key": "d1-3b",
                "type": "decision",
                "format": "gguf",
                "decision_type": "lfm2-d1",
                "loaded_instances": [{"id": "d1-instance"}],
            }
        ]
    }


def answer():
    return {
        "answers": {
            "rarity": {
                "choice": "L4",
                "confidence": 0.4,
                "probabilities": {"L1": 0.05, "L2": 0.05, "L3": 0.1, "L4": 0.7, "L5": 0.1},
            }
        }
    }


class D1ScorerTests(unittest.TestCase):
    def test_scores_original_spelling_with_explicit_levels_and_full_distribution(self):
        http = Mock()
        http.get.return_value = response(models())
        http.post.return_value = response(answer())
        scorer = D1Scorer(model="d1-3b", http=http)
        outcomes = scorer.score_batch([BaseWordRow(12, "țârâit", "noun")])
        self.assertEqual(outcomes[0].word_id, 12)
        self.assertEqual(outcomes[0].rarity_level, 4)
        self.assertEqual(outcomes[0].probabilities, (0.05, 0.05, 0.1, 0.7, 0.1))
        self.assertAlmostEqual(outcomes[0].expected_level, 3.75)
        request = http.post.call_args.kwargs["json"]
        self.assertEqual(request["model"], "d1-instance")
        self.assertEqual(request["state"]["word"], "țârâit")
        self.assertEqual(
            set(request["questions"]["rarity"]["criteria"]), {"L1", "L2", "L3", "L4", "L5"}
        )

    def test_exact_form_contract_keeps_all_pos_and_does_not_restrict_to_inventory_type(self):
        http = Mock()
        http.get.return_value = response(models())
        http.post.return_value = response(answer())
        contract = {
            1: dict(
                word="tău",
                inventory_type="N",
                loc_entries=[dict(pos="N"), dict(pos="P")],
                contexts=[],
            )
        }
        outcome = D1Scorer(model="d1-3b", http=http, form_contract=contract).score_batch(
            [BaseWordRow(1, "tău", "N")]
        )[0]
        state = outcome.request["state"]
        self.assertEqual(state["word"], "tău")
        self.assertNotIn("type", state)
        self.assertEqual(state["inventory_type"], "N")
        self.assertEqual(state["form_contract"]["loc_entries"], [dict(pos="N"), dict(pos="P")])
        instructions = outcome.request["questions"]["rarity"]["instructions"]
        self.assertIn("most familiar valid sense", instructions)
        self.assertIn("all valid parts of speech", instructions)
        self.assertIn("Do not substitute", instructions)
        http.reset_mock()
        with self.assertRaises(ValueError):
            D1Scorer(model="d1-3b", http=http, form_contract=contract).score_batch(
                [BaseWordRow(1, "tau", "N")]
            )
        http.get.assert_not_called()
        http.post.assert_not_called()

    def test_unloaded_or_wrong_model_never_triggers_an_inference_request(self):
        for model in [
            dict(models()["models"][0], loaded_instances=[]),
            dict(models()["models"][0], type="llm"),
            dict(models()["models"][0], key="other"),
        ]:
            with self.subTest(model=model):
                http = Mock()
                http.get.return_value = response({"models": [model]})
                with self.assertRaisesRegex(ValueError, "loaded decision"):
                    D1Scorer(model="d1-3b", http=http).score_batch([BaseWordRow(1, "casă", "")])
                http.post.assert_not_called()

    def test_invalid_distributions_are_explicit_failures_not_rare_predictions(self):
        invalid = []
        for value in [float("nan"), float("inf"), True, -0.1, 1.1, "0.7"]:
            body = answer()
            body["answers"]["rarity"]["probabilities"]["L4"] = value
            invalid.append(body)
        body = answer()
        body["answers"]["rarity"]["probabilities"].pop("L5")
        invalid.append(body)
        body = answer()
        body["answers"]["rarity"]["probabilities"]["L0"] = 0
        invalid.append(body)
        body = answer()
        body["answers"]["rarity"]["probabilities"]["L4"] = 0.2
        invalid.append(body)
        invalid += [{"answers": {}}, {"answers": dict(answer()["answers"], extra={})}]
        for body in invalid:
            with self.subTest(body=body):
                http = Mock()
                http.get.return_value = response(models())
                http.post.return_value = response(body)
                outcome = D1Scorer(model="d1-3b", http=http).score_batch(
                    [BaseWordRow(1, "casă", "")]
                )[0]
                self.assertEqual(outcome.status, "failed")
                self.assertIsNone(outcome.rarity_level)
                self.assertTrue(outcome.error)

    def test_duplicate_json_keys_fail_and_request_failure_does_not_skip_later_words(self):
        import requests

        http = Mock()
        http.get.return_value = response(models())
        duplicate = response({})
        duplicate.text = '{"answers":{"rarity":{},"rarity":{}}}'
        http.post.side_effect = [duplicate, requests.Timeout("timeout"), response(answer())]
        outcomes = D1Scorer(model="d1-3b", http=http).score_batch(
            [BaseWordRow(i, "cuvânt", "") for i in (1, 2, 3)]
        )
        self.assertEqual([o.status for o in outcomes], ["failed", "failed", "scored"])
        self.assertIn("Duplicate", outcomes[0].error)

    def test_evidence_and_serial_request_order_are_preserved(self):
        http = Mock()
        events = []

        def get(*args, **kwargs):
            events.append("preflight")
            return response(models())

        def post(url, **kwargs):
            events.append(kwargs["json"]["state"]["word"])
            return response(answer())

        http.get.side_effect = get
        http.post.side_effect = post
        scorer = D1Scorer(model="d1-3b", http=http, evidence={1: {"definition": "locuință"}})
        scorer.score_batch([BaseWordRow(1, "casă", ""), BaseWordRow(2, "ac", "")])
        self.assertEqual(events, ["preflight", "casă", "preflight", "ac"])
        self.assertEqual(
            http.post.call_args_list[0].kwargs["json"]["state"]["evidence"],
            {"definition": "locuință"},
        )

    def test_identity_change_aborts_before_another_inference(self):
        http = Mock()
        changed = models()
        changed["models"][0]["loaded_instances"] = [{"id": "replacement"}]
        http.get.side_effect = [response(models()), response(changed)]
        http.post.return_value = response(answer())
        with self.assertRaisesRegex(ValueError, "changed"):
            D1Scorer(model="d1-3b", http=http).score_batch(
                [BaseWordRow(1, "ac", ""), BaseWordRow(2, "casă", "")]
            )
        self.assertEqual(http.post.call_count, 1)

    def test_raw_exchange_is_available_for_audit(self):
        http = Mock()
        http.get.return_value = response(models())
        http.post.return_value = response(answer())
        outcome = D1Scorer(model="d1-3b", http=http).score_batch([BaseWordRow(1, "casă", "")])[0]
        self.assertEqual(outcome.request["state"]["word"], "casă")
        self.assertEqual(json.loads(outcome.response), answer())

    def test_probability_threshold_retains_abstained_distribution(self):
        http = Mock()
        http.get.return_value = response(models())
        http.post.return_value = response(answer())
        scorer = D1Scorer(model="d1-3b", http=http, min_probability=0.8)
        outcome = scorer.score_batch([BaseWordRow(1, "ac", "")])[0]
        self.assertEqual(outcome.status, "unresolved")
        self.assertEqual(outcome.rarity_level, 4)
        self.assertEqual(outcome.probabilities[3], 0.7)

    def test_preflight_returns_pin_without_inference_and_configuration_can_be_reused(self):
        http = Mock()
        http.get.return_value = response(models())
        scorer = D1Scorer(model="d1-3b", http=http)
        pin = scorer.preflight()
        self.assertEqual(pin["loaded_instances"][0]["id"], "d1-instance")
        http.post.assert_not_called()
