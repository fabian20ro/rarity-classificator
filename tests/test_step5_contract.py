import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import unittest
from unittest.mock import MagicMock
from dataclasses import dataclass
from classificator.steps.step5_rebalance import (
    run_step5, Step5Options, LevelTransition
)
from classificator.models import ScoreResult, LmApiFlavor
from classificator.lm.client import LmStudioClient
from classificator.run_csv_repository import RunCsvRepository

class TestStep5Contract(unittest.TestCase):
    def setUp(self: "TestStep5Contract"):
        self.run_slug = "test-contract"
        self.base_dir = Path(__file__).parent.parent.parent / "test_tmp"
        self.input_csv = self.base_dir / "test_input.csv"
        self.output_csv = self.base_dir / "test_output.csv"
        self.output_dir = self.base_dir / "test_output_dir"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create dummy input CSV
        with open(self.input_csv, "w") as f:
            f.write("word_id,word,type,rarity_level\n")
            f.write("1,apple,noun,1\n")
            f.write("2,banana,noun,1\n")
            f.write("3,cherry,noun,1\n")

        self.lm_client = MagicMock(spec=LmStudioClient)
        self.lm_client.resolve_endpoint.return_value = MagicMock(
            endpoint="http://localhost:1234",
            flavor=LmApiFlavor.LMSTUDIO_REST
        )
        
        self.repo = MagicMock(spec=RunCsvRepository)
        
        class MockTable:
            headers = ["word_id", "word", "type", "rarity_level"]
            def __init__(self, records):
                self.records = records
            def get(self, name):
                return None
        
        self.mock_records = [
            {"word_id": 1, "word": "apple", "type": "noun", "rarity_level": 1},
            {"word_id": 2, "word": "banana", "type": "noun", "rarity_level": 1},
            {"word_id": 3, "word": "cherry", "type": "noun", "rarity_level": 1},
        ]
        self.repo.read_table.return_value = MockTable(self.mock_records)

        def mock_write_table_atomic(path, headers, rows):
            with open(path, "w") as f:
                f.write(",".join(headers) + "\n")
                for row in rows:
                    f.write(",".join(map(str, row)) + "\n")
        
        self.repo.write_table_atomic.side_effect = mock_write_table_atomic
        
        # Mock transitions (all mapping 1 -> 1 for simplicity)
        transition = LevelTransition(from_level=1, to_level=1)
        self.options = Step5Options(
            run_slug=self.run_slug,
            model="test-model",
            input_csv_path=self.input_csv,
            output_csv_path=self.output_csv,
            transitions=[transition],
            dry_run=False,
            batch_size=10
        )

    def tearDown(self):
        import shutil
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)

    def test_output_has_no_zero_ids(self):
        # Mock LM returning exactly 1 word_id (as expected by the adaptive target)
        # In our case, expected_target_total = round(3 * 0.3333) = 1
        mock_scores = [
            ScoreResult(word_id=1, word="apple", type="noun", rarity_level=1, tag="test", confidence=1.0),
        ]
        self.lm_client.score_batch_resilient.return_value = mock_scores

        run_step5(self.options, repo=self.repo, lm_client=self.lm_client, output_dir=self.output_dir)

        # Check the output CSV
        self.assertTrue(self.output_csv.exists(), "Output file was not created")
        with open(self.output_csv, "r") as f:
            lines = f.readlines()
            # The first line is header
            for line in lines[1:]:
                if "," in line:
                    # Check that word_id is not 0
                    self.assertFalse(line.startswith("0,"), f"Found 0 as word_id in output: {line}")

if __name__ == "__main__":
    unittest.main()
