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

if __name__ == '__main__':
    unittest.main()
