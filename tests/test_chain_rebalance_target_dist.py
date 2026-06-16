import unittest
from pathlib import Path
from unittest.mock import MagicMock
from src.classificator.tools.chain_rebalance_target_dist import run_chain_rebalance, ChainOptions
from src.classificator.run_csv_repository import RunCsvRepository
from src.classificator.lm.client import LmStudioClient
from src.classificator.transitions import LevelTransition

class TestChainRebalance(unittest.TestCase):
    def test_small_total_words_raises_value_error(self):
        from src.classificator.csv_codec import CsvCodec
        
        class MockRunCsvRepository(RunCsvRepository):
            def read_table(self, path):
                class MockTable:
                    headers = ["word_id", "word", "type", "rarity_level", "confidence"]
                    records = [
                        MagicMock(values=["1", "test", "test", "1", "1.0"], line_number=2)
                    ]
                return MockTable()
            def load_run_rows(self, path):
                return []

        repo = MockRunCsvRepository()
        lm_client = MagicMock(spec=LmStudioClient)
        
        options = ChainOptions(
            input_csv=Path("dummy.csv"),
            model="test_model",
            run_base="test_run",
            runs_dir=Path("dummy_runs"),
            state_file=Path("dummy_state"),
            resume=False,
            final_output_csv=None,
            batch_size=1,
            max_tokens=100,
            timeout_seconds=10,
            max_retries=0,
            system_prompt_file=Path("dummy_system_prompt.txt"),
            user_template_file=Path("dummy_user_template.txt"),
            reference_csv=None,
            anchor_l1_file=None,
            min_l1_jaccard=None,
            min_anchor_l1_precision=None,
            min_anchor_l1_recall=None,
            endpoint_option=None,
            base_url_option=None,
        )
        
        # Create dummy files to satisfy Path checks
        Path("dummy_system_prompt.txt").touch()
        Path("dummy_user_template.txt").touch()
        Path("dummy.csv").touch()
        Path("dummy_runs").mkdir(exist_ok=True)
        Path("dummy_state").touch()

        try:
            with self.assertRaises(ValueError) as cm:
                run_chain_rebalance(
                    options=options,
                    repo=repo,
                    lm_client=lm_client,
                    output_dir=Path("dummy_output")
                )
            self.assertIn("Invalid target distribution", str(cm.exception))
        finally:
            # Cleanup
            for f in ["dummy.csv", "dummy_system_prompt.txt", "dummy_user_template.txt", "dummy_state"]:
                if Path(f).exists(): Path(f).unlink()
            if Path("dummy_runs").exists(): import shutil; shutil.rmtree("dummy_runs")
            if Path("dummy_output").exists(): import shutil; shutil.rmtree("dummy_output")

if __name__ == "__main__":
    unittest.main()
