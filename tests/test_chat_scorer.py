import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from classificator.lm.client import LmStudioClient, ScoringContext
from classificator.models import BaseWordRow, LmApiFlavor
from classificator.scoring.chat import ChatScorer


class ChatScorerTests(unittest.TestCase):
    def test_existing_chat_response_crosses_the_same_scoring_interface(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = ScoringContext(
                "test",
                "test-model",
                "http://unused/v1/chat/completions",
                1,
                2,
                Path(tmp) / "run.jsonl",
                Path(tmp) / "failed.jsonl",
                "Classify",
                "{{INPUT_JSON}}",
                LmApiFlavor.OPENAI_COMPAT,
                200,
            )
            body = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "results": [
                                        {
                                            "word_id": 12,
                                            "word": "casă",
                                            "type": "noun",
                                            "rarity_level": 1,
                                            "tag": "common",
                                            "confidence": 0.9,
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            }
            reply = Mock(status_code=200, text=json.dumps(body))
            reply.json.return_value = body
            with patch("requests.post", return_value=reply):
                outcomes = ChatScorer(LmStudioClient(api_key=None), context).score_batch(
                    [BaseWordRow(12, "casă", "noun")]
                )
            self.assertEqual(outcomes[0].rarity_level, 1)
            self.assertEqual(outcomes[0].probabilities, ())
            self.assertEqual(outcomes[0].confidence, 0.9)
