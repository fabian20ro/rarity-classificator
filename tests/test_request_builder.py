import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
