import unittest
import csv
import os
import tempfile
from pathlib import Path

from src.classificator.steps.step5_rebalance import (
    run_step5,
    Step5Options,
)
from src.classificator.run_csv_repository import RunCsvRepository
from src.classificator.lm.client import LmStudioClient, ScoringContext
from src.classificator.models import ScoreResult, ScoringOutputMode, BaseWordRow
from src.classificator.transitions import LevelTransition
from unittest.mock import MagicMock, patch

class MockTable:
    def __init__(self, headers, records):
        self.headers = headers
        self.records = records

class TestStep5Contract(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_path = Path(self.temp_dir.name)
        self.input_csv = self.temp_dir_path / "input.csv"
        self.output_csv = self.temp_dir_path / "output.csv"
        self.run_slug = "test_contract_run"

        # 1. Prepare input CSV with valid levels
        with open(self.input_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["word_id", "word", "type", "rarity_level"])
            writer.writerow(["1", "apple", "fruit", "1"])
            writer.writerow(["2", "banana", "fruit", "2"])
            writer.writerow(["3", "carrot", "veg", "3"])

        # Mocking dependencies
        self.mock_lm_client = MagicMock(spec=LmStudioClient)
        self.mock_lm_client.resolve_endpoint.return_value = MagicMock(
            endpoint="http://localhost:1234/v1",
            flavor="openai",
            source="mock"
        )
        self.mock_lm_client.preflight.return_value = None
        
        self.patcher = patch('src.classificator.steps.step5_rebalance.RunCsvRepository')
        self.MockRepoClass = self.patcher.start()
        self.mock_repo = self.MockRepoClass.return_value
        
        self.mock_repo.read_table.return_value = MockTable(
            headers=["word_id", "word", "type", "rarity_level"],
            records=[
                {"word_id": 1, "word": "apple", "type": "fruit", "rarity_level": 1},
                {"word_id": 2, "word": "banana", "type": "fruit", "rarity_level": 2},
                {"word_id": 3, "word": "carrot", "type": "veg", "rarity_level": 3},
            ]
        )
        
        self.output_dir = self.temp_dir_path / "outputs"
        self.output_dir.mkdir()

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def mock_write_table_atomic(self, path, headers, rows):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)

    def test_no_zero_local_id(self):
        transitions = [
            LevelTransition(from_level=1, to_level=2),
            LevelTransition(from_level=2, to_level=1),
            LevelTransition(from_level=3, to_level=2),
        ]

        options = Step5Options(
            run_slug=self.run_slug,
            model="mock-model",
            input_csv_path=self.input_csv,
            output_csv_path=self.output_csv,
            batch_size=10,
            lower_ratio=0.5,
            skip_preflight=True,
            dry_run=False,
            transitions=transitions
        )
        
        def mock_score_batch_resilient(batch_rows, scoring_ctx):
            results = []
            for row in batch_rows:
                wid = str(row.word_id)
                results.append(ScoreResult(
                    word_id=int(row.word_id),
                    rarity_level=2,
                    confidence=1.0
                ))
            return results
        self.mock_lm_client.score_batch_resilient.side_effect = mock_score_batch_resilient

        self.mock_repo.write_table_atomic.side_effect = self.mock_write_table_atomic

        run_step5(
            options=options,
            repo=self.mock_repo,
            lm_client=self.mock_lm_client,
            output_dir=self.output_dir
        )

        with open(self.output_csv, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['final_level'] == '0':
                    self.fail(f"Found local_id (final_level) equal to 0 in output CSV: {row}")

if __name__ == "__main__":
    unittest.main()
