import unittest
from classificator.batch_size_adapter import BatchSizeAdapter

class TestPackageIntegrity(unittest.TestCase):
    def test_batch_size_adapter_import(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        self.assertEqual(adapter.current_size, 10)

    def test_batch_size_adapter_scaling(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=2, window_size=3)
        # Test increase
        adapter.current_size = 4
        adapter.record_outcome(1.0)  # outcomes=[True], rate=1.0 -> size = min(10, 6) = 6
        self.assertEqual(adapter.current_size, 6)
        adapter.record_outcome(1.0)  # outcomes=[True, True], rate=1.0 -> size = min(10, 9) = 9
        self.assertEqual(adapter.current_size, 9)
        adapter.record_outcome(1.0)  # outcomes=[True, True, True], rate=1.0 -> size = min(10, 10) = 10
        self.assertEqual(adapter.current_size, 10)

        # Test decrease
        adapter.current_size = 10
        adapter.record_outcome(0.0)  # outcomes=[True, True, False], rate=0.66
        self.assertEqual(adapter.current_size, 10)
        adapter.record_outcome(0.0)  # outcomes=[True, False, False], rate=0.33 -> size = max(2, 6) = 6
        self.assertEqual(adapter.current_size, 6)
        adapter.record_outcome(0.0)  # outcomes=[False, False, False], rate=0.0 -> size = max(2, 4) = 4
        self.assertEqual(adapter.current_size, 4)

if __name__ == "__main__":
    unittest.main()
