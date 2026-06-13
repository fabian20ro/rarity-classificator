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

if __name__ == "__main__":
    unittest.main()
