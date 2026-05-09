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

    def test_selected_word_ids_rejects_out_of_range_ids(self):
        body = self._wrap_content("[999]")
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
        # 'casă' in batch, but 'casa' in response (no diacritics)
        body = self._wrap_content('[{"word_id": 102, "word": "casa", "type": "N", "rarity_level": 2, "tag": "test", "confidence": 1.0}]')
        parsed = self.parser.parse(
            batch=self.batch,
            response_body=body,
            output_mode=ScoringOutputMode.SCORE_RESULTS,
            forced_rarity_level=None,
            expected_items=None,
        )
        self.assertEqual(len(parsed.scores), 1)
        self.assertEqual(parsed.scores[0].word_id, 102)


if __name__ == "__main__":
    unittest.main()
