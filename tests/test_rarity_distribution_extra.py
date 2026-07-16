import unittest
import tempfile
from pathlib import Path
import csv
from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.rarity_distribution import run_rarity_distribution

class TestRarityDistributionExtra(unittest.TestCase):
    def setUp(self):
        self.repo = RunCsvRepository()
    def test_invalid_string_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'bad.csv'
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['word_id', 'word', 'rarity_level'])
                writer.writerow(['1', 'om', 'not_an_int'])
            with self.assertRaises(ValueError):
                run_rarity_distribution(csv_path=path, repo=self.repo)

    def test_valid_input_returns_correct_distribution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'good.csv'
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['word_id', 'word', 'rarity_level'])
                for lid in (1, 2, 3, 4):
                    writer.writerow([str(lid), f'word{lid}', str(lid)])
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
        self.assertEqual(result.total_rows, 4)
        self.assertEqual(list(sorted(result.distribution.items())), [(1, 1), (2, 1), (3, 1), (4, 1), (5, 0)])
        self.assertEqual(result.mode, 1)

    def test_empty_csv_header_only_returns_zero_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'empty.csv'
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['word_id', 'word', 'rarity_level'])
            result = run_rarity_distribution(csv_path=path, repo=self.repo)
        self.assertEqual(result.total_rows, 0)
        self.assertEqual(list(sorted(result.distribution.items())), [(1, 0), (2, 0), (3, 0), (4, 0), (5, 0)])
        self.assertEqual(result.mode, 1)

    def test_missing_level_column_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'nomatch.csv'
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['word_id', 'word'])
                writer.writerow(['1', 'om'])
            with self.assertRaises(ValueError):
                run_rarity_distribution(csv_path=path, repo=self.repo)

    def test_explicit_final_level_column_used(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'final.csv'
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['word_id', 'word', 'final_level'])
                writer.writerow(['1', 'alpha', '1'])
                writer.writerow(['2', 'beta', '1'])
                writer.writerow(['3', 'gamma', '4'])
            result = run_rarity_distribution(csv_path=path, repo=self.repo, level_column='final_level')
        self.assertEqual(result.total_rows, 3)
        self.assertEqual(result.level_column, 'final_level')
        self.assertEqual(list(sorted(result.distribution.items())), [(1, 2), (2, 0), (3, 0), (4, 1), (5, 0)])
        self.assertEqual(result.mode, 1)

    def test_explicit_median_level_column_used(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'median.csv'
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['word_id', 'word', 'median_level'])
                writer.writerow(['1', 'alpha', '2'])
                writer.writerow(['2', 'beta', '3'])
                writer.writerow(['3', 'gamma', '3'])
            result = run_rarity_distribution(csv_path=path, repo=self.repo, level_column='median_level')
        self.assertEqual(result.total_rows, 3)
        self.assertEqual(result.level_column, 'median_level')
        self.assertEqual(list(sorted(result.distribution.items())), [(1, 0), (2, 1), (3, 2), (4, 0), (5, 0)])
        self.assertEqual(result.mode, 3)


if __name__ == '__main__':
    unittest.main()
