import unittest
import csv
import os
from pathlib import Path
from unittest.mock import MagicMock
import sys

# Ensure src is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from classificator.steps.step5_rebalance import run_step5, Step5Options
from classificator.run_csv_repository import RunCsvRepository
from classificator.lm.client import LmStudioClient, ResolvedEndpoint, ScoringContext
from classificator.transitions import LevelTransition
from classificator.csv_codec import CsvRecord, CsvTable

class TestStep5Contract(unittest.TestCase):
    def setUp(self: None):
        self.test_dir = Path("/tmp/test_word_rarity_classifier")
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True)
        
        self.input_csv = self.test_dir / "input.csv"
        self.output_csv = self.test_dir / "output_actual.csv"
        self.logs_dir = self.test_dir / "logs"
        self.logs_dir.mkdir()

        # Prepare dummy input
        with open(self.input_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['word_id', 'word', 'type', 'final_level'])
            writer.writerow(['1', 'apple', 'fruit', '2'])
            writer.writerow(['2', 'banana', 'fruit', '2'])
            writer.writerow(['3', 'carrot', 'veg', '1'])

        # Mocking dependencies
        self.mock_repo = MagicMock(spec=RunCsvRepository)
        
        # Create actual CsvRecord objects to avoid mock issues
        records = [
            CsvRecord(line_number=2, values=['1', 'apple', 'fruit', '2']),
            CsvRecord(line_number=3, values=['2', 'banana', 'fruit', '2']),
            CsvRecord(line_number=4, values=['3', 'carrot', 'veg', '1']),
        ]
        mock_table = CsvTable(headers=['word_id', 'word', 'type', 'final_level'], records=records)
        self.mock_repo.read_table.return_value = mock_table
        
        def side_effect_write_table_atomic(path, headers, rows):
            target_path = path if isinstance(path, Path) else self.test_dir / "output_actual.csv"
            with open(target_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow(row)
        self.mock_repo.write_table_atomic.side_effect = side_effect_write_table_atomic

        self.mock_lm = MagicMock(spec=LmStudioClient)
        
        # Fix the flavor mock
        mock_flavor = MagicMock()
        mock_flavor.value = "test"
        
        self.mock_lm.resolve_endpoint.return_value = MagicMock(
            endpoint="http://localhost:1234", 
            flavor=mock_flavor, 
            source="mock"
        )
        
        self.mock_lm.score_batch_resilient.return_value = [
            MagicMock(word_id=1, rarity_level=2),
            MagicMock(word_id=2, rarity_level=2),
            MagicMock(word_id=3, rarity_level=1),
        ]

    def test_no_zero_local_ids(self):
        options = Step5Options(
            run_slug="test-contract",
            model="test-model",
            input_csv_path=self.input_csv,
            output_csv_path=self.output_csv,
            transitions=[LevelTransition(from_level=1, to_level=2)],
            skip_preflight=True,
            seed=42
        )

        run_step5(options, repo=self.mock_repo, lm_client=self.mock_lm, output_dir=self.test_dir)

        # Verify output file exists and check for 0s
        actual_outputs = list(self.test_dir.glob("*.csv"))
        if not actual_outputs:
            self.fail("No output CSV was produced")
        
        with open(actual_outputs[0], 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.assertNotEqual(int(row['word_id']), 0)

if __name__ == "__main__":
    unittest.main()
