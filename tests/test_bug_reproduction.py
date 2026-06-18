import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from classificator.steps.step4_upload import _build_full_fallback_plan, UploadMode
from classificator.models import WordLevel

class TestStep4Bug(unittest.TestCase):
    def test_build_full_fallback_plan_status_completeness(self):
        # Mocking inputs
        final_levels = {1: 1, 2: 2}
        db_levels = {
            1: WordLevel(word_id=1, rarity_level=1),
            2: WordLevel(word_id=2, rarity_level=2),
            3: WordLevel(word_id=3, rarity_level=3),
        }
        
        updates, report_rows, status = _build_full_fallback_plan(
            final_levels,
            db_levels
        )
        
        # updates should contain all db_levels in fallback mode
        self.assertEqual(len(updates), len(db_levels))
        # status should contain all updated words
        self.assertEqual(len(status), len(updates))
        self.assertIn(1, status)
        self.assertIn(2, status)
        self.assertIn(3, status)

if __name__ == "__main__":
    unittest.main()
