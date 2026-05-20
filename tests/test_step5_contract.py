import unittest
import unittest
from unittest.mock import MagicMock
from pathlib import Path
import csv
import shutil
import sys

sys.path.append("/workspace/git/word-rarity-classifier/src")

from classificator.steps.step5_rebalance import run_step5, Step5Options
from classificator.transitions import LevelTransition
from classificator.csv_codec import CsvRecord

class TestStep5Contract(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("/tmp/word-rust-test")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        self.input_csv = self.test_dir / "input.csv"
        self.output_csv = self.test_dir / "output.csv"
        
        with open(self.input_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["word_id", "word", "type", "final_level"])
            writer.writerow(["1", "apple", "fruit", "1"])
            writer.writerow(["2", "banana", "fruit", "2"]) 
            writer.writerow(["3", "carrot", "veg", "1"])

        self.run_slug = "test-run"
        self.options = Step5Options(
            run_slug=self.run_slug,
            model="test-model",
            input_csv_path=self.input_csv,
            output_csv_path=self.output_csv,
            transitions=[LevelTransition(from_level=2, to_level=1)],
            skip_preflight=True 
        )

    def test_rebalance_prevents_zero_id(self):
        mock_repo = MagicMock()
        class MockTable:
            def __init__(self, headers, records):
                self.headers = headers
                self.records = records
        
        mock_records = [
            CsvRecord(line_number=2, values=["1", "apple", "fruit", "1"]),
            CsvRecord(line_number=3, values=["2", "banana", "fruit", "2"]),
            CsvRecord(line_number=4, values=["3", "carrot", "veg", "1"]),
        ]
        mock_table = MockTable(
            headers=["word_id", "word", "type", "final_level"],
            records=mock_records
        )
        mock_repo.read_table.return_value = mock_table

        # IMPLEMENT THE MISSING WRITE LOGIC IN MOCK
        def write_table_atomic(path, headers, rows):
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow(row)
        mock_repo.write_table_atomic.side_effect = write_table_atomic

        mock_lm = MagicMock()
        mock_lm.resolve_endpoint.return_value = MagicMock(endpoint="http://localhost", flavor=MagicMock(), source=MagicMock())
        mock_lm.score_batch_resilient.return_value = []

        run_step5(self.options, repo=mock_repo, lm_client=mock_lm, output_dir=self.test_dir)

        self.assertTrue(self.output_csv.exists())
        with open(self.output_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.assertNotEqual(row["word_id"], "0", f"Found word_id 0 in output CSV: {row}")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

if __name__ == "__main__":
    unittest.main()
