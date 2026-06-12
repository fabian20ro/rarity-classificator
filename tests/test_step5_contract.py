import unittest
import csv
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from classificator.steps.step5_rebalance import run_step5, Step5Options
from classificator.run_csv_repository import RunCsvRepository
from classificator.lm.client import LmStudioClient

class TestStep5Contract(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.gettempdir()) / "compound_test_step5"
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True)

        self.input_csv = self.test_dir / "input.csv"
        self.output_csv = self.test_dir / "output.csv"
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir()
        
        # Create dummy input CSV
        # Requirements for step5: word_id, word, type, rarity_level
        with open(self.input_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(["word_id", "word", "type", "rarity_level"])
            writer.writerow(["1", "apple", "noun", "1"])
            writer.writerow(["2", "run", "verb", "2"])
            writer.writerow(["3", "quickly", "adverb", "3"])

        self.mock_lm_client = MagicMock(spec=LmStudioClient)
        self.mock_repo = RunCsvRepository()
        
        # We need to ensure the rebalance logic doesn't crash when reading/writing to repo.
        # Since we're mocking nothing else, we'll rely on the file system.
        # We need to mock the return value of some calls if they interact with network/repos.
        # But for now, let's see.
        
    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_contract_no_zero_local_id(self):
        """Verify that the output CSV does not contain any local_id == 0."""
        
        # Step 5 requires transitions.
        # For simplicity, we'll just use a dummy valid transition.
        # The goal is to ensure the input word_ids are preserved and no 0 is introduced.
        from classificator.transitions import LevelTransition
        dummy_transition = LevelTransition(from_level=1, to_level=1)
        
        options = Step5Options(
            run_slug="test-run",
            model="test-model",
            input_csv_path=self.input_csv,
            output_csv_path=self.output_csv,
            batch_size=1,
            lower_ratio=0.5,
            max_retries=0,
            timeout_seconds=10,
            max_tokens=100,
            skip_preflight=True,
            dry_run=False,
            transitions=[dummy_transition] # Not empty
        )

        
        # We must mock some aspects of the LM client or it will crash.
        # But if transitions is empty, it shouldn't call the LLM much.
        # Let's check the code. _apply_transition is called for each transition.
        # If transitions is empty, it just writes the input to output.
        
        run_step5(
            options,
            repo=self.mock_repo,
            lm_client=self.mock_lm_client,
            output_dir=self.output_dir
        )
        
        self.assertTrue(self.output_csv.exists())
        
        with open(self.output_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.assertNotEqual(row["word_id"], "0", f"Found 0 as word_id in output: {row}")
                self.assertNotEqual(int(row["word_id"]), 0)

if __name__ == "__main__":
    unittest.main()
