import unittest
from pathlib import Path
from unittest.mock import MagicMock
from src.classificator.tools.chain_rebalance_target_dist import run_chain_rebalance, ChainOptions
from src.classificator.run_csv_repository import RunCsvRepository
from src.classificator.lm.client import LmStudioClient
from src.classificator.transitions import LevelTransition

class TestChainRebalance(unittest.TestCase):

    def setUp(self):
        for f in ["dummy.csv", "dummy_system_prompt.txt", "dummy_user_template.txt", "dummy_state"]:
            if Path(f).exists():
                Path(f).unlink()
        if Path("dummy_runs").exists():
            import shutil
            shutil.rmtree("dummy_runs")
        if Path("dummy_output").exists():
            import shutil
            shutil.rmtree("dummy_output")

    def test_count_total_words_basic(self):
        from src.classificator.tools.chain_rebalance_target_dist import _count_total_words

        class MockTable:
            headers = ["word_id", "word"]
            records = [MagicMock()] * 5

        class MockRepo(RunCsvRepository):
            def read_table(self, path):
                return MockTable()
            def load_run_rows(self, path):
                return []

        count = _count_total_words(Path("dummy.csv"), MockRepo())
        self.assertEqual(count, 5)

    def test_get_level_count_rarity_level_column(self):
        from src.classificator.tools.chain_rebalance_target_dist import _get_level_count

        class MockTable:
            headers = ["word_id", "rarity_level"]
            records = [
                MagicMock(values=["1", "1"]),
                MagicMock(values=["2", "2"]),
                MagicMock(values=["3", "2"]),
                MagicMock(values=["4", "1"]),
            ]

        class MockRepo(RunCsvRepository):
            def read_table(self, path):
                return MockTable()
            def load_run_rows(self, path):
                return []

        count = _get_level_count(Path("dummy.csv"), 2, MockRepo())
        self.assertEqual(count, 2)

    def test_get_level_count_final_level_column(self):
        from src.classificator.tools.chain_rebalance_target_dist import _get_level_count

        class MockTable:
            headers = ["word_id", "final_level"]
            records = [
                MagicMock(values=["1", "3"]),
                MagicMock(values=["2", "3"]),
                MagicMock(values=["3", "5"]),
            ]

        class MockRepo(RunCsvRepository):
            def read_table(self, path):
                return MockTable()
            def load_run_rows(self, path):
                return []

        count = _get_level_count(Path("dummy.csv"), 3, MockRepo())
        self.assertEqual(count, 2)

    def test_get_level_count_invalid_column_raises(self):
        from src.classificator.tools.chain_rebalance_target_dist import _get_level_count

        class MockTable:
            headers = ["word_id", "level"]
            records = []

        class MockRepo(RunCsvRepository):
            def read_table(self, path):
                return MockTable()
            def load_run_rows(self, path):
                return []

        with self.assertRaises(ValueError) as cm:
            _get_level_count(Path("dummy.csv"), 1, MockRepo())
        self.assertIn("final_level or rarity_level", str(cm.exception))

    def test_get_level_count_handles_malformed_values_gracefully(self):
        from src.classificator.tools.chain_rebalance_target_dist import _get_level_count

        class MockTable:
            headers = ["word_id", "rarity_level"]
            records = [
                MagicMock(values=["1", "2"]),
                MagicMock(values=["2", "abc"]),  # non-numeric value
                MagicMock(values=["3", "3.5"]),   # float string in int column
                MagicMock(values=["4", "2"]),
            ]

        class MockRepo(RunCsvRepository):
            def read_table(self, path):
                return MockTable()
            def load_run_rows(self, path):
                return []

        count = _get_level_count(Path("dummy.csv"), 2, MockRepo())
        self.assertEqual(count, 2)  # Records 0 and 3 have rarity_level == "2"

    def test_get_level_count_non_numeric_skips_record(self):
        from src.classificator.tools.chain_rebalance_target_dist import _get_level_count

        class MockTable:
            headers = ["word_id", "rarity_level"]
            records = [
                MagicMock(values=["1", "not_a_number"]),  # invalid value
                MagicMock(values=["2", "1"]),
            ]

        class MockRepo(RunCsvRepository):
            def read_table(self, path):
                return MockTable()
            def load_run_rows(self, path):
                return []

        count = _get_level_count(Path("dummy.csv"), 1, MockRepo())
        self.assertEqual(count, 1)  # Only record 1 has rarity_level == 1; invalid skipped

    def test_sanitize_slug_strips_special_chars(self):
        from src.classificator.tools.chain_rebalance_target_dist import _sanitize_slug

        result = _sanitize_slug("S1_abc-def@#$!run")
        self.assertEqual(result, "s1_abc_defrun")

    def test_sanitize_slug_truncates_to_40(self):
        from src.classificator.tools.chain_rebalance_target_dist import _sanitize_slug

        long_name = "a" * 50
        result = _sanitize_slug(long_name)
        self.assertEqual(len(result), 40)

    def test_sanitize_slug_empty_after_clean_returns_default(self):
        from src.classificator.tools.chain_rebalance_target_dist import _sanitize_slug

        result = _sanitize_slug("@#$%")
        self.assertEqual(result, "rebalance_run")

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

    def test_step1_pool_too_small_raises_value_error(self):
        """Pool of 1 record should raise ValueError before any LLM call."""
        from src.classificator.tools.chain_rebalance_target_dist import run_chain_rebalance

        class MockTable:
            headers = ["word_id", "word", "type", "rarity_level", "confidence"]
            # All records at level 5; with valid total, step1 pool (l1+l2) is 0 -> too small.
            records = [
                MagicMock(values=["1", "test", "test", "5", "1.0"], line_number=2)
                for _ in range(60000)
            ]

        class MockRepo(RunCsvRepository):
            def read_table(self, path):
                return MockTable()
            def load_run_rows(self, path):
                return []

        repo = MockRepo()
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
            self.assertIn("pool too small", str(cm.exception))
        finally:
            for f in ["dummy.csv", "dummy_system_prompt.txt", "dummy_user_template.txt", "dummy_state"]:
                if Path(f).exists(): Path(f).unlink()
            if Path("dummy_runs").exists(): import shutil; shutil.rmtree("dummy_runs")
            if Path("dummy_output").exists(): import shutil; shutil.rmtree("dummy_output")

if __name__ == "__main__":
    unittest.main()
