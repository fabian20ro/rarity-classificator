import unittest
import tempfile
import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

from classificator.run_csv_repository import RunCsvRepository
from classificator.steps.step5_rebalance import run_step5, Step5Options
from classificator.transitions import LevelTransition
from classificator.models import LmApiFlavor

class TestStep5Contract(unittest.TestCase):
    def setUp(self):
        self.repo = RunCsvRepository()
        self.td = tempfile.TemporaryDirectory()
        self.tmp_rag_dir = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    @patch("classificator.steps.step5_rebalance._prepare_logs")
    @patch("classificator.steps.step5_rebalance.LmStudioClient")
    def test_no_zero_local_id(self, MockLmClient, mock_prepare_logs):
        # Setup paths
        input_csv = self.tmp_rag_dir / "input.csv"
        output_csv = self.tmp_rag_dir / "output.csv"
        log_dir = self.tmp_rag_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # 1. Prepare input CSV (word_id, word, type, rarity_level)
        headers = ["word_id", "word", "type", "rarity_level"]
        rows = [
            ["101", "test1", "noun", "3"],
            ["102", "test2", "verb", "2"],
            ["103", "test3", "adj", "4"],
        ]
        with input_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        # 2. Mock Logs
        mock_logs = MagicMock()
        mock_logs.run_log_path = log_dir / "run.log"
        mock_logs.failed_log_path = log_dir / "failed.log"
        mock_logs.switched_words_log_path = log_dir / "switched.log"
        mock_logs.checkpoint_path = log_dir / "checkpoint"
        mock_logs.progress_log_path = log_dir / "progress.log"
        mock_prepare_logs.return_value = mock_logs

        # 3. Mock LmClient and scoring
        mock_client = MockLmClient()
        mock_client.resolve_endpoint.return_value = MagicMock(
            endpoint="http://localhost:1234",
            flavor=LmApiFlavor.OPENAI_COMPAT,
            source="manual"
        )
        # Return empty scores so no changes occur
        mock_client.score_batch_resilient.return_value = []

        # 4. Setup Transitions (e.g., 3 -> 2)
        transitions = [LevelTransition(from_level=3, to_level=2)]
        
        options = Step5Options(
            run_slug="test-run",
            model="gpt-4o",
            input_csv_path=input_csv,
            output_csv_path=output_csv,
            batch_size=10,
            skip_preflight=True,
            transitions=transitions,
        )

        # 5. Run Step 5
        run_step5(options, repo=self.repo, lm_client=mock_client, output_dir=log_dir)

        # 6. Verify Output CSV
        self.assertTrue(output_csv.exists())
        
        table = self.repo.read_table(output_csv)
        ids = []
        for rec in table.records:
            row = dict(zip(table.headers, rec.values))
            ids.append(int(row["word_id"]))

        self.assertNotIn(0, ids)
        self.assertEqual(len(ids), 3)

if __name__ == "__main__":
    unittest.main()
