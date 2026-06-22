import unittest
from src.classificator.batch_size_adapter import BatchSizeAdapter

class TestPackageSmoke(unittest.TestCase):
    def test_batch_size_adapter_import(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3)
        self.assertEqual(adapter.initial_size, 10)

if __name__ == "__main__":
    unittest.main()
