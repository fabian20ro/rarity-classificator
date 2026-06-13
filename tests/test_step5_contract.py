import unittest
import os
import csv
import subprocess
import tempfile
from pathlib import Path

class TestStep5Contract(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.input_csv = Path(self.test_dir.name) / "input.csv"
        self.output_csv = Path(self.test_dir.name) / "output.csv"
        self.test_run_slug = "test-contract-run"
        
        # Create a dummy input CSV with valid levels and unique local_ids 1..N
        with open(self.input_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["word_id", "rarity_level", "word", "type"])
            writer.writerow(["1", "1", "apple", "fruit"])
            writer.writerow(["2", "2", "banana", "fruit"])
            writer.writerow(["3", "1", "cherry", "fruit"])
            writer.writerow(["4", "3", "date", "fruit"])

    def tearDown(self):
        self.test_dir.cleanup()

    def test_no_zero_local_id(self):
        # We'll run the actual CLI to see if it respects the contract
        cmd = [
            "uv", "run", "python", "-m", "classificator.cli", "step5-rebalance",
            "--run", self.test_run_slug,
            "--model", "gpt-4o",
            "--input-csv", str(self.input_csv),
            "--output-csv", str(self.output_csv),
            "--batch-size", "10",
            "--skip-preflight"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            self.fail(f"CLI failed with error: {result.stderr}")
            
        if not self.output_csv.exists():
            self.fail("Output CSV was not created.")

        with open(self.output_csv, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # local_id should be >= 1 according to the plan/policy
                word_id = int(row["word_id"])
                self.assertGreaterEqual(word_id, 1, f"Found word_id {word_id} in output CSV")

if __name__ == "__main__":
    unittest.main()
