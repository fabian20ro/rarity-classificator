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


if __name__ == '__main__':
    unittest.main()
