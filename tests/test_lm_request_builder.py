import unittest
from pathlib import Path
from unittest.mock import MagicMock
from classificator.lm.request_builder import LmStudioRequestBuilder, JsonSchemaKind, ResponseFormatMode
from classificator.models import ScoringOutputMode, LmModelConfig, BaseWordRow

class TestLmStudioRequestBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = LmStudioRequestBuilder()
        self.base_payload = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "hello"}],
        }
        self.config = LmModelConfig(model_id="test-model", temperature=0.0)
        self.batch = [BaseWordRow(word_id=1, word="apple", type="noun")]

    def test_missing_expected_items_raises(self):
        with self.assertRaises(ValueError) as cm:
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="system",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_SCHEMA,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=100,
                expected_items=0,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )
        self.assertIn("expected_items is required", str(cm.exception))

    def test_zero_expected_items_raises(self):
        with self.assertRaises(ValueError) as cm:
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="system",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_SCHEMA,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=100,
                expected_items=0,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )
        self.assertIn("expected_items is required", str(cm.exception))

    def test_valid_payload_score_results(self):
        payload_str = self.builder.build_request(
            model="test-model",
            batch=self.batch,
            system_prompt="system",
            user_template="user",
            response_format_mode=ResponseFormatMode.JSON_SCHEMA,
            include_reasoning_controls=False,
            config=self.config,
            max_tokens=100,
            expected_items=1,
            schema_kind=JsonSchemaKind.SCORE_RESULTS,
        )
        import json
        payload = json.loads(payload_str)
        self.assertIn("response_format", payload)
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertIn("items", payload["response_format"]["json_schema"]["schema"])
        self.assertIn("word_id", payload["response_format"]["json_schema"]["schema"]["items"]["properties"])

    def test_different_response_format_mode(self):
        payload_str = self.builder.build_request(
            model="test-model",
            batch=self.batch,
            system_prompt="system",
            user_template="user",
            response_format_mode=ResponseFormatMode.JSON_OBJECT,
            include_reasoning_controls=False,
            config=self.config,
            max_tokens=100,
        )
        import json
        payload = json.loads(payload_str)
        self.assertEqual(payload["response_format"]["type"], "json_object")

    def test_selected_word_ids_schema_builds_valid_payload(self):
        payload_str = self.builder.build_request(
            model="test-model",
            batch=self.batch,
            system_prompt="system",
            user_template="user",
            response_format_mode=ResponseFormatMode.JSON_SCHEMA,
            include_reasoning_controls=False,
            config=self.config,
            max_tokens=100,
            expected_items=1,
            schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
        )
        import json
        payload = json.loads(payload_str)
        self.assertIn("response_format", payload)
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["items"]["minimum"], 1)
        self.assertEqual(schema["items"]["maximum"], len(self.batch))
        self.assertTrue(schema["uniqueItems"])

    def test_selected_word_ids_exceeds_batch_raises(self):
        with self.assertRaises(ValueError) as cm:
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="system",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_SCHEMA,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=100,
                expected_items=999,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )
        self.assertIn("cannot exceed batch size", str(cm.exception))

    def test_config_passthrough_includes_top_k_and_repeat_penalty(self):
        import json

        config = LmModelConfig(
            model_id="test-model", temperature=0.0, top_k=42, repeat_penalty=1.5
        )
        payload = json.loads(
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="system",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_OBJECT,
                include_reasoning_controls=False,
                config=config,
                max_tokens=100,
            )
        )
        self.assertEqual(payload["top_k"], 42)
        self.assertEqual(payload["repeat_penalty"], 1.5)

    def test_include_reasoning_controls_injects_effort_and_kwargs(self):
        config = LmModelConfig(
            model_id="test-model", temperature=0.0, reasoning_effort="high"
        )
        import json

        payload = json.loads(
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="system",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_OBJECT,
                include_reasoning_controls=True,
                config=config,
                max_tokens=100,
            )
        )
        self.assertEqual(payload["reasoning_effort"], "high")

    def test_user_template_without_placeholder_appends_entries(self):
        import json

        user_template = "Analyze these words."
        payload = json.loads(
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="system",
                user_template=user_template,
                response_format_mode=ResponseFormatMode.JSON_OBJECT,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=100,
            )
        )
        content = payload["messages"][1]["content"]
        self.assertIn("apple", content)

if __name__ == "__main__":
    unittest.main()
