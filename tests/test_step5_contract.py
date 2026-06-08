import unittest
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Setup for local test execution
sys.path.append(str(Path(__file__).parent.parent / "src"))

from classificator.steps.step5_rebalance import _select_common_word_ids

class ScoreResultMock:
    def __init__(self, wid, rl):
        self.word_id = wid
        self.rarity_level = rl

class RebalanceWord:
    def __init__(self, word_id, word, type):
        self.word_id = word_id
        self.word = word
        self.type = type

class TestStep5Contract(unittest.TestCase):
    def test_select_common_word_ids_rejects_zero(self):
        """Verify that _select_common_word_ids rejects word_id=0 even if scoring returns it."""
        batch = [
            RebalanceWord(word_id=1, word="apple", type="fruit"),
            RebalanceWord(word_id=2, word="banana", type="fruit"),
            RebalanceWord(word_id=0, word="bug", type="fruit")
        ]
        # Scored results where word_id 0 is returned by the LLM
        scored = [
            ScoreResultMock(1, 1),
            ScoreResultMock(2, 1),
            ScoreResultMock(0, 1)
        ]
        
        # Common level is 1
        common_level = 1
        # Expected count for common level (1 and 2)
        common_count = 2
        
        # The current implementation likely accepts it. We want to ensure it doesn't.
        # We'll call it and check if 0 is in the result.
        
        # We'll assume the implementation should be fixed to not include 0.
        
        try:
            selected = _select_common_word_ids(
                batch=batch,
                scored=scored,
                common_level=common_level,
                common_count=common_count
            )
            self.assertNotIn(0, selected, "The selected word IDs should not contain 0.")
        except Exception as e:
            self.fail(f"The function raised an unexpected exception: {e}")

if __name__ == "__main__":
    unittest.main()
