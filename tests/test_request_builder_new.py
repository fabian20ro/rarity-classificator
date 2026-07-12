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

    def test_max_tokens_cap_respected(self):
        config = LmModelConfig(model_id="test-model", max_tokens_cap=50)
        payload = json.loads(
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.NONE,
                include_reasoning_controls=False,
                config=config,
                max_tokens=512,
                expected_items=1,
                schema_kind=JsonSchemaKind.SCORE_RESULTS,
            )
        )
        self.assertEqual(payload["max_tokens"], 50)

    def test_selected_word_ids_schema_multi_item_bounds(self):
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
                expected_items=2,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )
        )

        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["minItems"], 2)
        self.assertEqual(schema["maxItems"], 2)
        self.assertTrue(schema["uniqueItems"])
        self.assertEqual(schema["items"], {"type": "integer", "minimum": 1, "maximum": 2})

    def test_json_object_mode_produces_no_json_schema_key(self):
        payload = json.loads(
            self.builder.build_request(
                model="test-model",
                batch=self.batch,
                system_prompt="sys",
                user_template="user",
                response_format_mode=ResponseFormatMode.JSON_OBJECT,
                include_reasoning_controls=False,
                config=self.config,
                max_tokens=512,
                expected_items=1,
                schema_kind=JsonSchemaKind.SELECTED_WORD_IDS,
            )
        )

        self.assertEqual(payload["response_format"], {"type": "json_object"})
