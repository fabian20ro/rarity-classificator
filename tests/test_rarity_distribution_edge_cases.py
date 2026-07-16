import tempfile
import unittest
from pathlib import Path

from classificator.distribution import RarityDistribution
from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.rarity_distribution import run_rarity_distribution


class RarityDistributionTest(unittest.TestCase):
    def setUp(self):
        self.repo = RunCsvRepository()

    def _write_csv(self, path: Path, headers: list[str], rows: list[list[str]]):
        self.repo.write_rows(path, headers, rows)

    def test_auto_detects_rarity_level(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "run.csv"
            self._write_csv(
                path,
                ["word_id", "word", "type", "rarity_level"],
                [["1", "om", "N", "1"], ["2", "casă", "N", "2"], ["3", "rar", "A", "5"]],
            )
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertEqual(result.level_column, "rarity_level")
            self.assertEqual(result.total_rows, 3)
            self.assertEqual(result.distribution[1], 1)
            self.assertEqual(result.distribution[2], 1)
            self.assertEqual(result.distribution[5], 1)

    def test_can_use_explicit_level_column(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "comparison.csv"
            self._write_csv(
                path,
                ["word_id", "word", "final_level", "median_level"],
                [["1", "om", "1", "2"], ["2", "casă", "3", "2"], ["3", "rar", "5", "4"]],
            )
            result = run_rarity_distribution(csv_path=path, level_column="median_level", repo=self.repo)
            self.assertEqual(result.level_column, "median_level")
            self.assertEqual(result.distribution[2], 2)
            self.assertEqual(result.distribution[4], 1)

    def test_invalid_level_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "bad.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "om", "0"]],
            )
            with self.assertRaises(ValueError):
                run_rarity_distribution(csv_path=path, repo=self.repo)

    def test_run_rarity_distribution_invalid_level_raises_high(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "bad.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "om", "6"]],
            )
            with self.assertRaises(ValueError):
                run_rarity_distribution(csv_path=path, repo=self.repo)

    def test_count_validates_level_range(self):
        dist = RarityDistribution.from_levels([1, 2, 3])
        self.assertEqual(dist.count(1), 1)
        with self.assertRaises(ValueError):
            dist.count(0)
        with self.assertRaises(ValueError):
            dist.count(6)

    def test_count_returns_zero_for_unincremented_level(self):
        dist = RarityDistribution.from_levels([1, 1])
        self.assertEqual(dist.count(2), 0)

    def test_total_returns_sum_of_counts(self):
        dist = RarityDistribution.from_levels([1, 2, 3, 3, 5])
        self.assertEqual(dist.total, 5)

    def test_total_is_zero_for_empty_distribution(self):
        dist = RarityDistribution()
        self.assertEqual(dist.total, 0)

    def test_format_uses_total_property(self):
        dist = RarityDistribution.from_levels([1, 1])
        formatted = dist.format()
        self.assertIn("1:2", formatted)
        self.assertIn("100.0%", formatted)

    def test_set_level_moves_count_between_levels(self):
        dist = RarityDistribution.from_levels([1, 2, 3])
        self.assertEqual(dist.count(1), 1)
        self.assertEqual(dist.count(3), 1)

    def test_increment_silent_duplicate_inflates_counts(self):
        dist = RarityDistribution()
        dist.increment(3)
        dist.increment(3)
        self.assertEqual(dist.count(3), 2)
        self.assertEqual(dist.total, 2)

    def test_from_levels_allows_duplicates(self):
        dist = RarityDistribution.from_levels([1, 1, 1])
        self.assertEqual(dist.count(1), 3)
        self.assertEqual(dist.total, 3)

    def test_run_rarity_distribution_missing_column_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "missing.csv"
            self._write_csv(
                path,
                ["word_id", "word"],
                [["1", "om"]],
            )
            with self.assertRaises(ValueError):
                run_rarity_distribution(csv_path=path, repo=self.repo)

    def test_empty_csv_produces_zero_total(self):
        """Header-only CSV (no data rows) should yield an empty distribution."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "empty.csv"
            self._write_csv(path, ["word_id", "word", "rarity_level"], [])
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertEqual(result.total_rows, 0)
            dist = RarityDistribution.from_levels([])
            self.assertEqual(dist.total, 0)

    def test_single_row_yields_one_entry(self):
        """A single-row CSV must produce a total of one."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "single.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "test", "3"]],
            )
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertEqual(result.total_rows, 1)
            self.assertEqual(result.distribution[3], 1)

    def test_all_same_level_uniform(self):
        """When every row shares the same rarity level, distribution is uniform."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "uniform.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "a", "2"], ["2", "b", "2"], ["3", "c", "2"]],
            )
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertEqual(result.total_rows, 3)
            self.assertEqual(result.distribution[2], 3)

    def test_format_mixed_levels(self):
        """format() output for a mixed distribution should include all observed levels."""
        dist = RarityDistribution.from_levels([1, 2, 3, 4, 5])
        formatted = dist.format()
        self.assertIn("1:1", formatted)
        self.assertIn("2:1", formatted)
        self.assertIn("3:1", formatted)
        self.assertIn("4:1", formatted)
        self.assertIn("5:1", formatted)

    def test_extra_columns_do_not_break_detection(self):
        """A CSV with additional columns beyond the expected ones must still detect rarity_level."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "extra.csv"
            self._write_csv(
                path,
                ["word_id", "word", "type", "rarity_level", "frequency"],
                [["1", "om", "N", "1", "500"]],
            )
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertEqual(result.level_column, "rarity_level")

    def test_boundary_level_five_accepts(self):
        """Level 5 is the maximum valid rarity level and must be accepted."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "max.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "ultrarare", "5"]],
            )
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertEqual(result.distribution[5], 1)

if __name__ == "__main__":
    unittest.main()
