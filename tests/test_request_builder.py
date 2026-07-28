import json
import unittest
from pathlib import Path

from classificator.lm.request_builder import (
    JsonSchemaKind,
    LmStudioRequestBuilder,
    ResponseFormatMode,
)
from classificator.models import BaseWordRow, LmModelConfig


class RequestBuilderTest(unittest.TestCase):
    def setUp(self):
        self.builder = LmStudioRequestBuilder()
        self.batch = [
            BaseWordRow(word_id=101, word="om", type="N"),
            BaseWordRow(word_id=102, word="casă", type="N"),
        ]
        self.config = LmModelConfig(model_id="test-model")

    def test_selected_word_ids_schema_uses_exact_count_and_unique_items(self):
        payload = json.loads(
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_SCHEMA,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=512,
                expected_items=1,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )
        )

        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["type"], "array")
        self.assertEqual(schema["minItems"], 1)
        self.assertEqual(schema["maxItems"], 1)
        self.assertTrue(schema["uniqueItems"])
        self.assertEqual(schema["items"], {"type": "integer", "minimum": 1, "maximum": 2})

    def test_selected_word_ids_schema_requires_expected_count(self):
        with self.assertRaises(ValueError):
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_SCHEMA,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=512,
                expected_items=None,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )

    def test_selected_word_ids_schema_rejects_impossible_expected_count(self):
        with self.assertRaises(ValueError):
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_SCHEMA,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=512,
                expected_items=3,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )

    def test_selected_word_ids_require_positive_expected_count_even_without_json_schema(self):
        with self.assertRaises(ValueError):
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.NONE,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=512,
                expected_items=0,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )

    def test_selected_word_ids_reject_impossible_expected_count_even_without_json_schema(self):
        with self.assertRaises(ValueError):
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.NONE,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=512,
                expected_items=3,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )

    def test_reasoning_controls(self):
        config = LmModelConfig(model_id="test-model", reasoning_effort="high", enable_thinking=True)
        payload = json.loads(
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.NONE,
                include_reasoning_controls=True,
                config=config,
                max_tokens=512,
                expected_items=1,
                schema_kind=JsonSchemaKind.SCORE_RESULTS,
            )
        )
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertEqual(payload["chat_template_kwargs"]["enable_thinking"], True)

    def test_reasoning_controls_preserves_all_fields_when_multiple_set(self):
        config = LmModelConfig(
            model_id="test-model",
            reasoning_effort="medium",
            enable_thinking=True,
            thinking_type="disabled",
        )
        payload = json.loads(
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.NONE,
                include_reasoning_controls=True,
                config=config,
                max_tokens=512,
                expected_items=1,
                schema_kind=JsonSchemaKind.SCORE_RESULTS,
            )
        )
        self.assertEqual(payload["reasoning_effort"], "medium")
        kwargs = payload["chat_template_kwargs"]
        self.assertTrue(kwargs["enable_thinking"])
        self.assertEqual(kwargs["thinking_type"], "disabled")

    def test_selected_word_ids_schema_rejects_non_positive_expected_items(self):
        with self.assertRaises(ValueError):
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_SCHEMA,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=512,
                expected_items=0,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )

    def test_selected_word_ids_schema_accepts_positive_expected_items(self):
        payload = json.loads(
            self.builder.build_request(
                model="test-model",
                batch=self.batch * 5,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_SCHEMA,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=512,
                expected_items=5,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )
        )
        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["minItems"], 5)
        self.assertEqual(schema["maxItems"], 5)

    def test_build_request_rejects_empty_batch(self):
        with self.assertRaises(ValueError) as ctx:
            self.builder.build_request(
                model="test-model",
                batch=[],
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.NONE,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=512,
            )
        self.assertIn("batch must contain at least one word", str(ctx.exception))

    def test_score_results_mode_requires_positive_expected_items_when_specified(self):
        with self.assertRaises(ValueError) as ctx:
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_SCHEMA,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=512,
                expected_items=-1,
                schema_kind=JsonSchemaKind.SCORE_RESULTS,
            )
        self.assertIn("expected_items must be positive", str(ctx.exception))

    def test_build_request_rejects_non_positive_max_tokens(self):
        with self.assertRaises(ValueError) as ctx:
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.NONE,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=0,
            )
        self.assertIn("max_tokens must be positive", str(ctx.exception))

    def test_user_template_without_placeholder_uses_input_prefix(self):
        config = LmModelConfig(model_id="test-model")
        user_template = "Clasifică aceste cuvinte:"
        payload = json.loads(
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template=user_template,
                response_format_mode=ResponseFormatMode.NONE,
                include_reasoning_controls=False,
                config=config,
                max_tokens=512,
                expected_items=2,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )
        )
        user_content = payload["messages"][1]["content"]
        self.assertIn(user_template + "\n\nIntrări:", user_content)


if __name__ == "__main__":
    unittest.main()
