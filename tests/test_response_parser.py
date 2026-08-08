import json
import unittest

from classificator.lm.response_parser import LmStudioResponseParser
from classificator.models import BaseWordRow, ScoringOutputMode


class ResponseParserTest(unittest.TestCase):
    def setUp(self):
        self.parser = LmStudioResponseParser()
        self.batch = [
            BaseWordRow(word_id=101, word="om", type="N"),
            BaseWordRow(word_id=102, word="casă", type="N"),
        ]

    def _wrap_content(self, content: str) -> str:
        payload = {"choices": [{"message": {"content": content}}]}
        return json.dumps(payload, ensure_ascii=False)

    def test_selected_word_ids_accepts_valid_local_id(self):
        body = self._wrap_content("[1]")
        parsed = self.parser.parse(
            batch=self.batch,
            response_body=body,
            output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
            forced_rarity_level=1,
            expected_items=1,
        )
        self.assertEqual(len(parsed.scores), 1)
        self.assertEqual(parsed.scores[0].word_id, 101)
        self.assertEqual(parsed.scores[0].rarity_level, 1)

    def test_malformed_envelope_is_repaired(self):
        # Missing closing brace for the root object
        body = '{"choices": [{"message": {"content": "[1]"}}]'
        parsed = self.parser.parse(
            batch=self.batch,
            response_body=body,
            output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
            forced_rarity_level=1,
            expected_items=1,
        )
        self.assertEqual(len(parsed.scores), 1)
        self.assertEqual(parsed.scores[0].word_id, 101)
        self.assertEqual(parsed.scores[0].rarity_level, 1)

    def test_selected_word_ids_rejects_word_id_fallback(self):
        # Should NOT allow word_id as a fallback in dict mode to prevent corruption
        body = self._wrap_content('[{"word_id": 102, "word": "wrong", "type": "N", "rarity_level": 1, "tag": "test", "confidence": 1.0}]')
        with self.assertRaises(RuntimeError):
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
                forced_rarity_level=1,
                expected_items=1,
            )

    def test_selected_word_ids_rejects_zero_based_positions(self):
        body = self._wrap_content("[0]")
        with self.assertRaises(RuntimeError) as ctx:
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
                forced_rarity_level=1,
                expected_items=1,
            )
        self.assertIn("out of range", str(ctx.exception))

    def test_selected_word_ids_enforces_exact_count(self):
        body = self._wrap_content("[1]")
        with self.assertRaises(RuntimeError):
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
                forced_rarity_level=1,
                expected_items=2,
            )

    def test_selected_word_ids_rejects_duplicate_local_ids(self):
        body = self._wrap_content("[1, 1]")
        with self.assertRaises(RuntimeError):
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
                forced_rarity_level=1,
                expected_items=1,
            )

    def test_selected_word_ids_rejects_duplicate_local_ids_across_shapes(self):
        body = self._wrap_content('[1, {"local_id": 1, "word": "om"}]')
        with self.assertRaises(RuntimeError):
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
                forced_rarity_level=1,
                expected_items=1,
            )

    def test_selected_word_ids_rejects_duplicate_local_ids_across_numeric_strings(self):
        body = self._wrap_content('["1", {"local_id": "1", "word": "om"}]')
        with self.assertRaises(RuntimeError):
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
                forced_rarity_level=1,
                expected_items=1,
            )

    def test_score_results_parsing(self):
        body = self._wrap_content('[{"word_id": 102, "word": "casă", "type": "N", "rarity_level": 2, "tag": "test", "confidence": 1.0}]')
        parsed = self.parser.parse(
            batch=self.batch,
            response_body=body,
            output_mode=ScoringOutputMode.SCORE_RESULTS,
            forced_rarity_level=None,
            expected_items=None,
        )
        self.assertEqual(len(parsed.scores), 1)
        self.assertEqual(parsed.scores[0].word_id, 102)
        self.assertEqual(parsed.scores[0].rarity_level, 2)

    def test_score_results_rejects_float_ids(self):
        body = self._wrap_content('[{"word_id": 102.5, "word": "casă", "type": "N", "rarity_level": 2, "tag": "test", "confidence": 1.0}]')
        with self.assertRaises(RuntimeError) as ctx:
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SCORE_RESULTS,
                forced_rarity_level=None,
                expected_items=None,
            )
        self.assertIn("missing or invalid word_id", str(ctx.exception))

    def test_selected_word_ids_strips_code_fences_from_model_content(self):
        body = self._wrap_content("```json\n[1]\n```")
        parsed = self.parser.parse(
            batch=self.batch,
            response_body=body,
            output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
            forced_rarity_level=1,
            expected_items=1,
        )
        self.assertEqual(len(parsed.scores), 1)
        self.assertEqual(parsed.scores[0].word_id, 101)

    def test_selected_word_ids_multi_selection_via_dict_nodes(self):
        batch = [
            BaseWordRow(word_id=201, word="a", type="N"),
            BaseWordRow(word_id=202, word="b", type="N"),
            BaseWordRow(word_id=203, word="c", type="N"),
        ]
        body = self._wrap_content(
            '[{"local_id": 1, "word": "a"}, {"local_id": 3, "word": "c"}]'
        )
        parsed = self.parser.parse(
            batch=batch,
            response_body=body,
            output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
            forced_rarity_level=2,
            expected_items=2,
        )
        returned_ids = sorted(s.word_id for s in parsed.scores)
        self.assertEqual(returned_ids, [201, 203])

    def test_extract_results_array_rejects_multiple_list_values(self):
        body = self._wrap_content(
            '{"foo": [1], "bar": ["extra"]}'
        )
        with self.assertRaises(RuntimeError) as ctx:
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SCORE_RESULTS,
                forced_rarity_level=None,
                expected_items=None,
            )
        self.assertIn("multiple list values", str(ctx.exception))

    def test_score_results_propagates_invalid_rarity_as_error(self):
        body = self._wrap_content(
            '[{"word_id": 102, "word": "casă", "type": "N", "rarity_level": 99}]'
        )
        with self.assertRaises(RuntimeError) as ctx:
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SCORE_RESULTS,
                forced_rarity_level=None,
                expected_items=None,
            )
        self.assertIn("No valid results parsed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
