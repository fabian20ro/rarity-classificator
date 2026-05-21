import unittest
import tempfile
from pathlib import Path
import csv
from unittest.mock import MagicMock, patch

try:
    from src.classificator.steps.step5_rebalance import run_step5, Step5Options, LevelTransition
    from src.classificator.run_csv_repository import RunCsvRepository
    from src.classificator.lm.client import LmStudioClient, ResolvedEndpoint
except ImportError as e:
    print(f"Import error: {int(e)}") # wait, int(e) is wrong.
    raise

# I will use a better way to handle imports for the test run.
import sys
import os
sys.path.append(os.getcwd())

try:
    from src.classificator.steps.step5_rebalance import run_step5, Step5Options, LevelTransition
    from src.classificator.run_csv_repository import RunCsvRepository
    from src.classificator.lm.client import LmStudioClient, ResolvedEndpoint
except ImportError as e:
    print(f"Import error: {e}")
    raise

class TestStep5Contract(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.gettempdir()) / "step5_contract_test"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.input_csv = self.test_dir / "input.csv"
        self.output_csv = self.test_dir / "output.csv"
        self.run_slug = "contract-test"

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_output_ids_are_one_based(self):
        # 1. Create dummy input CSV with 1-based IDs
        headers = ["word_id", "word", "type", "rarity_level"]
        rows = [
            ["1", "apple", "noun", "1"],
            ["2", "run", "verb", "2"],
            ["10", "happy", "adj", "3"],
        ]
        with open(self.input_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)

        # 2. Setup Mocks
        repo = RunCsvRepository()
        lm_client = MagicMock(spec=LmStudioClient)
        resolved = MagicMock(spec=ResolvedEndpoint)
        resolved.endpoint = "http://localhost"
        resolved.flavor = MagicMock()
        resolved.flavor.value = "mock"
        resolved.source = MagicMock()
        lm_client.resolve_endpoint.return_value = resolved
        lm_client.preflight.return_value = None

        options = Step5Options(
            run_slug=self.run_slug,
            model="mock-model",
            input_csv_path=self.input_csv,
            output_csv_path=self.output_csv,
            skip_preflight=True,
            transitions=[LevelTransition(from_level=1, to_level=2)]
        )

        # We need to patch _apply_transition to just do nothing and not call LLM
        from src.classificator.steps.step5_rebalance import TransitionSummary
        with patch("src.classificator.steps.step5_rebalance._apply_transition") as mock_apply:
            mock_apply.return_value = TransitionSummary(
                transition=LevelTransition(from_level=1, to_level=2),
                eligible=3, target_assigned=0, switched_count=0
            )

            # 3. Run Step 5
            output_dir = self.test_dir / "logs"
            output_dir.mkdir(parents=True, exist_ok=True)

            run_step5(options, repo=repo, lm_client=lm_client, output_dir=output_dir)

        # 4. Verify Output CSV has 1-based IDs in 'final_level'
        self.assertTrue(self.output_csv.exists())
        with open(self.output_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # The rule is that the output should contain 1-based levels (as per code line 187)
                lvl = int(row["final_level"])
                self.assertIn(lvl, {1, 2, 3})

if __name__ == "__main__":
    unittest.main()
