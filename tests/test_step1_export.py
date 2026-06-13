import unittest
from pathlib import Path
from unittest.mock import MagicMock
from src.classificator.steps.step1_export import run_step1, Step1Options
from src.classificator.run_csv_repository import RunCsvRepository
from src.classificator.word_store import WordStore
from dataclasses import dataclass

@dataclass
class MockWord:
    word_id: int
    word: str
    type: str

class MockWordStore(WordStore):
    def __init__(self, words):
        self.words = words
    def fetch_all_words(self):
        return self.words

class TestStep1Export(unittest.TestCase):
    def setUp(self):
        self.output_csv = Path("test_output.csv")
        if self.output_csv.exists():
            self.output_csv.unlink()
        
        self.mock_repo = MagicMock(spec=RunCsvRepository)
        
        self.words = [
            MockWord(1, "apple", "fruit"),
            MockWord(2, "banana", "fruit"),
        ]
        self.mock_word_store = MockWordStore(self.words)

    def tearDown(self):
        if self.output_csv.exists():
            self.output_csv.unlink()

    def test_run_step1_success(self):
        options = Step1Options(output_csv_path=self.output_csv)
        result_path = run_step1(options, word_store=self.mock_word_store, repo=self.mock_repo)
        
        self.assertEqual(result_path, self.output_csv)
        self.mock_repo.write_rows.assert_called_once()
        # Check headers and data
        args, _ = self.mock_repo.write_rows.call_args
        headers = args[1]
        rows = args[2]
        self.assertEqual(headers, ["word_id", "word", "type"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], ["1", "apple", "fruit"])
        self.assertEqual(rows[1], ["2", "banana", "fruit"])

if __name__ == "__main__":
    unittest.main()
