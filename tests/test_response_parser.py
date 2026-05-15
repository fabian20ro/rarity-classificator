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

    def test_selected_word_ids_rejects_word_id_fallback(self):
        # Should NOT allow word_id as a fallback in dict mode to prevent corruption
        # We provide word_id=102 (which is index 2 in batch, but not local_id 1 or 2)
        # and a word that doesn't match anything in the batch.
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
        body = self._wrap_content('[0]')
        with self.assertRaises(RuntimeError):
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
                forced_rarity_level=1,
                expected_items=1,
            )

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

    def test_selected_word_ids_rejects_out_of_range_local_ids(self):
        body = self._wrap_content("[1, 3]")
        with self.assertRaises(RuntimeError):
            self.parser.parse(
                batch=self.batch,
                response_body=body,
                output_mode=ScoringOutputMode.SELECTED_WORD_IDS,
                forced_rarity_level=1,
                expected_items=1,
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
        # Testing the scoring mode with a valid dict response
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

if __name__ == "__main__":
    unittest.main()
