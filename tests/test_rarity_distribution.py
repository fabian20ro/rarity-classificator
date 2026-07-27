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
                [["1", "om", "N", "1"], ["2", "casă", "N", "2"], ["3", "rar", "A", "5"], ["4", "test", "X", "1"]],
            )
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertEqual(result.level_column, "rarity_level")
            self.assertEqual(result.total_rows, 4)
            self.assertEqual(result.distribution[1], 2)
            self.assertEqual(result.distribution[2], 1)
            self.assertEqual(result.distribution[5], 1)
            self.assertEqual(result.mode, 1)

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
        dist.set_level(previous_level=2, new_level=4)
        self.assertEqual(dist.count(1), 1)
        self.assertEqual(dist.count(2), 0)
        self.assertEqual(dist.count(3), 1)
        self.assertEqual(dist.count(4), 1)

    def test_set_level_with_none_previous_only_increments(self):
        dist = RarityDistribution()
        dist.set_level(previous_level=None, new_level=3)
        self.assertEqual(dist.count(3), 1)
        self.assertEqual(dist.total, 1)

    def test_set_level_preserves_total(self):
        dist = RarityDistribution.from_levels([1, 2, 3, 4, 5])
        before_total = dist.total
        dist.set_level(previous_level=2, new_level=4)
        self.assertEqual(dist.total, before_total)

    def test_set_level_invalid_new_level_raises(self):
        dist = RarityDistribution.from_levels([1, 2, 3])
        with self.assertRaises(ValueError):
            dist.set_level(previous_level=1, new_level=6)

    def test_invalid_row_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "bad.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "om", "1"], ["2", "casă", ""], ["3", "rar", "5"]],
            )
            with self.assertRaises(ValueError) as cm:
                run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertIn("Invalid rarity_level '' at row 3", str(cm.exception))

    def test_requested_level_column_missing_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "missing_col.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "om", "1"]],
            )
            with self.assertRaises(ValueError) as cm:
                run_rarity_distribution(csv_path=path, level_column="invalid_col", repo=self.repo)
            self.assertIn("CSV missing requested level column 'invalid_col'", str(cm.exception))

    def test_auto_detects_final_level_preferred_over_rarity_level(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "both.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level", "final_level"],
                [["1", "om", "3", "1"], ["2", "casă", "5", "2"]],
            )
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertEqual(result.level_column, "final_level")
            self.assertEqual(result.distribution[1], 1)
            self.assertEqual(result.distribution[2], 1)

    def test_empty_csv_without_level_column_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "empty.csv"
            self._write_csv(path, ["word_id", "word"], [])
            with self.assertRaises(ValueError) as cm:
                run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertIn("CSV missing level column", str(cm.exception))

    def test_blank_rarity_level_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "blanks.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "om", ""], ["2", "casă", ""]],
            )
            with self.assertRaises(ValueError) as cm:
                run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertIn("Invalid rarity_level '' at row 2", str(cm.exception))

    def test_mode_for_single_record(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "single.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "rar", "5"]],
            )
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertEqual(result.mode, 5)
            self.assertEqual(result.total_rows, 1)

    def test_mode_breaks_ties_returns_lowest_level(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "tied.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "a", "2"], ["2", "b", "2"], ["3", "c", "4"], ["4", "d", "4"]],
            )
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertEqual(result.mode, 2)

    def test_invalid_level_raises_specific_message(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "bad.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "om", "abc"]],
            )
            with self.assertRaises(ValueError) as cm:
                run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertIn("not a number", str(cm.exception))

    def test_range_invalid_raises_specific_message(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "bad.csv"
            self._write_csv(
                path,
                ["word_id", "word", "rarity_level"],
                [["1", "om", "0"]],
            )
            with self.assertRaises(ValueError) as cm:
                run_rarity_distribution(csv_path=path, repo=self.repo)
            self.assertIn("must be between 1 and 5", str(cm.exception))

    def test_non_string_level_raises_type_error(self):
        from classificator.tools.rarity_distribution import _validate_level

        with self.assertRaises(TypeError) as cm:
            _validate_level(None, "test_col", 1)  # type: ignore[arg-type]
        self.assertIn("Expected string level for test_col", str(cm.exception))

    def test_validate_level_accepts_valid_string(self):
        from classificator.tools.rarity_distribution import _validate_level

        self.assertEqual(_validate_level("3", "test_col", 1), 3)
