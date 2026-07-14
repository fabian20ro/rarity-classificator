import unittest
from pathlib import Path
from classificator.csv_codec import CsvCodec, CsvFormatError, CsvTable

class TestCsvCodec(unittest.TestCase):
    def setUp(self):
        self.codec = CsvCodec()
        self.test_dir = Path("/tmp/csv_codec_test")
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def test_read_table_success(self):
        path = self.test_dir / "test.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("id,name\n1,test_id\n2,test_name")
        
        table = self.codec.read_table(path)
        self.assertEqual(len(table.headers), 2)
        self.assertEqual(table.headers, ["id", "name"])
        self.assertEqual(len(table.records), 2)
        self.assertEqual(table.records[0].values, ["1", "test_id"])

    def test_read_table_empty_file(self):
        path = self.test_dir / "empty.csv"
        path.touch()
        with self.assertRaises(CsvFormatError):
            self.codec.read_table(path)

    def test_read_table_mismatched_columns(self):
        path = self.test_dir / "mismatch.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("id,name\n1,test_id,extra\n2,test_name")
        with self.assertRaises(CsvFormatError) as cm:
            self.codec.read_table(path)
        self.assertIn("has 3 columns, expected 2", str(cm.exception))

    def test_read_table_empty_header_cell(self):
        path = self.test_dir / "empty_cell.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(",name\n1,test_name")
        with self.assertRaises(CsvFormatError) as cm:
            self.codec.read_table(path)
        self.assertIn("header column 1 is empty", str(cm.exception))

    def test_read_table_trailing_blank_row_skipped(self):
        path = self.test_dir / "trailing_blank.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("id,name\n1,test_id\n2,test_name\n")
        table = self.codec.read_table(path)
        self.assertEqual(len(table.records), 2)

    def test_read_table_blank_row_in_middle_raises(self):
        path = self.test_dir / "blank_middle.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("id,name\n1,test_id\n\n2,test_name")
        with self.assertRaises(CsvFormatError) as cm:
            self.codec.read_table(path)
        self.assertIn("line 3 has 0 columns, expected 2", str(cm.exception))

    def test_write_table_atomic_roundtrip(self):
        path = self.test_dir / "atomic.csv"
        headers = ["a", "b"]
        rows = [["1", "x"], ["2", "y"]]
        self.codec.write_table_atomic(path, headers, rows)
        # tmp file should be removed after replace
        self.assertFalse((path.with_name("atomic.csv.tmp")).exists())
        table = self.codec.read_table(path)
        self.assertEqual(table.headers, headers)
        self.assertEqual(len(table.records), 2)

    def test_read_table_whitespace_header_cell_accepted(self):
        path = self.test_dir / "ws_header.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(" ,name\n1,test_name")
        # Current codec only checks `if not cell`, so whitespace passes.
        table = self.codec.read_table(path)
        self.assertEqual(table.headers[0], " ")

    def test_write_table_success(self):
        path = self.test_dir / "out.csv"
        headers = ["id", "name"]
        rows = [["1", "val1"], ["2", "val2"]]
        self.codec.write_table(path, headers, rows)
        
        table = self.codec.read_table(path)
        self.assertEqual(table.headers, headers)
        self.assertEqual(len(table.records), 2)

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

if __name__ == "__main__":
    unittest.main()
