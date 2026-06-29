import unittest
from classificator.batch_size_adapter import BatchSizeAdapter

class TestPackageIntegrity(unittest.TestCase):
    def test_batch_size_adapter_import(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        self.assertEqual(adapter.current_size, 10)
    def test_batch_size_adapter_scaling(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=2, window_size=3)
        self.assertEqual(adapter.current_size, 10)
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

    def test_scaling_thresholds(self):
        """Test the 0.5 and 0.9 thresholds for size adjustment."""
        # 0.9 threshold (increase)
        adapter = BatchSizeAdapter(initial_size=10, min_size=5, window_size=10)
        for _ in range(9):
            adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)  # rate = 0.9 (9/10 successes)
        self.assertEqual(adapter.current_size, 10)
        adapter.record_outcome(1.0)  # rate = 1.0 (10/10 successes)
        self.assertEqual(adapter.current_size, 10)

        # 0.5 threshold (decrease)
        adapter = BatchSizeAdapter(initial_size=10, min_size=2, window_size=10)
        for _ in range(5):
            adapter.record_outcome(1.0)
        for _ in range(5):
            adapter.record_outcome(0.0)
        # rate = 0.5. No change.
        self.assertEqual(adapter.current_size, 10)
        adapter.record_outcome(0.0)  # rate = 4/10 = 0.4. Decrease.
        self.assertEqual(adapter.current_size, 6)

    def test_scaling_limits(self):
        # Test max_size limit
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5, max_size=12)
        for _ in range(5):
            adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 12)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 12)

        # Test min_size limit
        adapter = BatchSizeAdapter(initial_size=10, min_size=5, window_size=5)
        for _ in range(5):
            adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 5)
        adapter.record_outcome(0.0)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 5)

    def test_trend_states(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=2, window_size=5)
        # Initially outcomes is empty, rate=1.0, trend="increasing"
        self.assertEqual(adapter.trend, "increasing")

        # Force stability
        # We need rate in [0.5, 0.9]. 3/5 = 0.6
        for _ in range(3):
            adapter.record_outcome(1.0)
        for _ in range(2):
            adapter.record_outcome(0.0)
        self.assertEqual(adapter.trend, "stable")

        # Force decreasing
        # rate < 0.5. e.g., 2/5 = 0.4
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.trend, "decreasing")
    unittest.main()
