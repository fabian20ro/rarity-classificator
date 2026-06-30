import unittest
from classificator.batch_size_adapter import BatchSizeAdapter

class TestBatchSizeAdapter(unittest.TestCase):
    def test_initialization(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        self.assertEqual(adapter.current_size, 10)
        with self.assertRaises(ValueError):
            BatchSizeAdapter(initial_size=2, min_size=3)
        with self.assertRaises(ValueError):
            BatchSizeAdapter(initial_size=10, min_size=0)
        with self.assertRaises(ValueError):
            BatchSizeAdapter(initial_size=10, window_size=0)
        with self.assertRaises(ValueError):
            BatchSizeAdapter(initial_size=10, low_threshold=0.5, high_threshold=0.5)
        with self.assertRaises(ValueError):
            BatchSizeAdapter(initial_size=10, low_threshold=0.6, high_threshold=0.5)

    def test_success_rate(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=3)
        self.assertEqual(adapter.success_rate(), 1.0)
        
        adapter.record_outcome(1.0) # Success
        self.assertEqual(adapter.success_rate(), 1.0)
        
        adapter.record_outcome(0.0) # Failure
        adapter.record_outcome(0.0) # Failure
        self.assertEqual(adapter.success_rate(), 1/3)

    def test_adjustment(self):
        # window_size=2, initial=10, min=3
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=2)
        
        # rate = 1.0 (successes)
        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 10) # current_size was 10, min(10, 15) = 10
        
        # rate = 0.5 (one success, one failure) -> success_rate=0.5 (not < 0.5, not > 0.9)
        # no adjustment
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 10)
        
        # rate = 1/3 < 0.5. current_size = max(3, (10 * 2) // 3) = 6
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 6)
        
        # rate = 1/3 (2/3 failures? no, 1/3)
        # outcomes: [True, False, False] -> window_size=2 -> [False, False]
        # rate = 0.0 < 0.5. current_size = max(3, (6 * 2) // 3) = 4
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 4)
        
        # rate = 1/2 (one success, one failure)
        # outcomes: [False, True] -> rate=0.5
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 4)

        # rate = 1.0 (two successes)
        # outcomes: [True, True] -> rate=1.0
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 6) # 4 * 1.5 = 6

    def test_window_size_limit(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=2)
        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        self.assertEqual(len(adapter.outcomes), 2)

    def test_reset(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        adapter.record_outcome(0.0)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 4)
        adapter.reset()
        self.assertEqual(adapter.current_size, 10)
        self.assertEqual(len(adapter.outcomes), 0)

    def test_recommended_size(self):
        adapter = BatchSizeAdapter(initial_size=10)
        self.assertEqual(adapter.recommended_size(), 10)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.recommended_size(), 6)

    def test_limits(self):
        # Test min_size limit
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=2)
        adapter.current_size = 3
        adapter.record_outcome(0.0)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 3)

        # Test initial_size limit
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=2)
        adapter.current_size = 10
        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 10)

        # Test max_size limit
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=2, max_size=15)
        adapter.current_size = 12
        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 15)

        # Test invalid max_size
        with self.assertRaises(ValueError):
            BatchSizeAdapter(initial_size=10, max_size=5)

    def test_success_thresholds(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        # 0.9 should be success
        adapter.record_outcome(0.9)
        self.assertTrue(adapter.outcomes[-1])
        # 0.89 should be failure
        adapter.record_outcome(0.89)
        self.assertFalse(adapter.outcomes[-1])
        # 1.1 should be success
        adapter.record_outcome(1.1)
        self.assertTrue(adapter.outcomes[-1])
        # -0.1 should be failure
        adapter.record_outcome(-0.1)
        self.assertFalse(adapter.outcomes[-1])

    def test_is_stable(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=2, low_threshold=0.4, high_threshold=0.6)
        # Rate 1.0 (increasing)
        adapter.record_outcome(1.0)
        self.assertFalse(adapter.is_stable)

        # Rate 0.5 (stable)
        adapter.record_outcome(0.0)
        self.assertTrue(adapter.is_stable)

        # Rate 0.0 (decreasing)
        adapter.record_outcome(0.0)
        self.assertFalse(adapter.is_stable)

    def test_get_metrics(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        metrics = adapter.get_metrics()
        self.assertEqual(metrics["current_size"], 10)
        self.assertEqual(metrics["success_rate"], 1.0)
        self.assertEqual(metrics["trend"], "increasing")
        self.assertFalse(metrics["is_stable"])
        self.assertEqual(metrics["window_usage"], 0)
        self.assertEqual(metrics["window_size"], 5)

        adapter.record_outcome(0.0)
        metrics = adapter.get_metrics()
        self.assertEqual(metrics["success_rate"], 0.0)
        self.assertEqual(metrics["trend"], "decreasing")
        self.assertFalse(metrics["is_stable"])
        self.assertEqual(metrics["window_usage"], 1)

    def test_adjustment_long_sequence(self):
        # Test a long sequence of successes to see if it reaches initial_size
        adapter = BatchSizeAdapter(initial_size=20, min_size=5, window_size=5)
        for _ in range(10):
            adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 20)

        # Test a long sequence of failures to see if it reaches min_size
        adapter = BatchSizeAdapter(initial_size=20, min_size=5, window_size=5)
        for _ in range(10):
            adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 5)

    def test_window_size_one(self):
        adapter = BatchSizeAdapter(initial_size=100, min_size=1, window_size=1)
        adapter.current_size = 10
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 15)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 22)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 14)

    def test_boundary_conditions(self):
        # window_size=10, initial=100, min=10
        adapter = BatchSizeAdapter(initial_size=100, min_size=10, window_size=10)
        # 1. Rate = 0.5 (5 successes, 5 failures) -> No change
        for _ in range(5):
            adapter.record_outcome(1.0)
        for _ in range(5):
            adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 100)
        # 2. Rate = 0.9 (9 successes, 1 failure) -> No change
        adapter = BatchSizeAdapter(initial_size=100, min_size=10, window_size=10)
        for _ in range(9):
            adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 100)
        # 3. Rate = 0.4 (4 successes, 6 failures) -> Decrease
        adapter = BatchSizeAdapter(initial_size=100, min_size=10, window_size=10)
        for _ in range(4):
            adapter.record_outcome(1.0)
        for _ in range(6):
            adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 44)

if __name__ == "__main__":
    unittest.main()
