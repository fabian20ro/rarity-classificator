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

    def test_set_level_with_invalid_previous_is_noop_on_decrement(self):
        dist = RarityDistribution.from_levels([1, 2])
        self.assertEqual(dist.count(2), 1)
        dist.set_level(previous_level=0, new_level=3)
        self.assertEqual(dist.count(2), 1)
        self.assertEqual(dist.count(3), 1)


if __name__ == "__main__":
    unittest.main()
