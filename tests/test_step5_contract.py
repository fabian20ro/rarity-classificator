import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import unittest
from unittest.mock import MagicMock
from src.classificator.steps.step5_rebalance import (
    _select_common_word_ids, RebalanceWord
)
from src.classificator.models import ScoreResult

class TestStep5Contract(unittest.TestCase):
    def test_no_zero_local_id(self):
        from src.classificator.steps.step5_rebalance import _select_common_word_ids
        
        # Mocking ScoreResult
        mock_result = MagicMock(spec=ScoreResult)
        mock_result.word_id = 0
        mock_result.rarity_level = 1
        
        batch = [RebalanceWord(word_id=1, word="hello", type="test")]
        scored = [mock_result]
        
        # Expecting RuntimeError because word_id 0 is ignored by:
        # if s.word_id in batch_ids and s.rarity_level == common_level and s.word_id not in seen and s.word_id > 0:
        with self.assertRaisesRegex(RuntimeError, "Expected exactly 1 selected word_ids, got 0"):
            _select_common_word_ids(batch=batch, scored=scored, common_level=1, common_count=1)

if __name__ == "__main__":
    unittest.main()
