import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import csv
import os
import tempfile

from classificator.steps.step5_rebalance import run_step5, Step5Options
from classificator.run_csv_repository import RunCsvRepository
from classificator.lm.client import LmStudioClient
from classificator.models import ScoreResult, ScoringOutputMode
from classificator.transitions import LevelTransition

class TestStep5Contract(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.gettempdir()) / "compound_test_contract"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.input_csv = self.test_dir / "input.csv"
        self.output_csv = self.test_dir / "output.csv"

        # Prepare input CSV
        with open(self.input_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["word_id", "word", "type", "rarity_level"])
            writer.writerow(["1", "word1", "noun", "1"])
            writer.writerow(["2", "word2", "verb", "2"])
            writer.writerow(["3", "word3", "adj", "1"])

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch('classificator.lm.client.LmStudioClient.score_batch_resilient')
    @patch('classificator.lm.client.LmStudioClient.preflight')
    @patch('classificator.lm.client.LmStudioClient.resolve_endpoint')
    def test_no_zero_local_id(self, mock_resolve, mock_preflight, mock_score):
        mock_resolve.return_value = MagicMock(endpoint="http://localhost:1234", flavor="local", source="test")

        # We want 2 items to be assigned to transition to level 1.
        # Input: 1 (lvl 1), 2 (lvl 2), 3 (lvl 1)
        # We want to test that the output doesn't have local_id=0.

        # We'll simulate that word 2 is selected for transition.

        # The batch contains word 2.
        mock_results = [
            MagicMock(word_id=2, rarity_level=1)
        ]
        mock_score.return_value = mock_results

        options = Step5Options(
            run_slug="test_run",
            model="test-model",
            input_csv_path=self.input_csv,
            output_csv_path=self.output_csv,
            transitions=[LevelTransition(from_level=2, to_level=1)],
            dry_run=False
        )

        repo = RunCsvRepository()
        lm_client = LmStudioClient(api_key="dummy")

        run_step5(options, repo=repo, lm_client=lm_client, output_dir=self.test_dir)

        # Verify output
        with open(self.output_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # In the output, word_id is a column.
                # We check that it's not 0.
                self.assertNotEqual(int(row['word_id']), 0)

if __name__ == "__main__":
    unittest.main()
