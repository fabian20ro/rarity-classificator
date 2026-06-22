import unittest
from src.classificator.batch_size_adapter import BatchSizeAdapter

class TestPackageSmoke(unittest.TestCase):
    def test_batch_size_adapter_import(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3)
        self.assertEqual(adapter.initial_size, 10)

    def test_batch_size_adapter_validation(self):
        with self.assertRaises(ValueError):
            BatchSizeAdapter(initial_size=1, min_size=2)

    def test_batch_size_adapter_rate_and_recommendation(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=2)
        adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.success_rate(), 0.5)
        self.assertEqual(adapter.current_size, 10)


if __name__ == "__main__":
    unittest.main()
