from __future__ import annotations

import unittest
from src.classificator.batch_size_adapter import BatchSizeAdapter

class TestBatchSizeAdapter(unittest.TestCase):
    def test_initialization(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=5, window_size=5)
        self.assertEqual(adapter.current_size, 10)
        self.assertEqual(adapter.recommended_size(), 10)

    def test_success_rate_all_ok(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=5, window_size=5)
        for _ in range(5):
            adapter.record_outcome(1.0)
        self.assertEqual(adapter.success_rate(), 1.0)
        self.assertEqual(adapter.recommended_size(), 10)

    def test_success_rate_all_fail(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=2, window_size=5)
        for _ in range(5):
            adapter.record_outcome(0.0)
        self.assertEqual(adapter.success_rate(), 0.0)
        
        # Reset to test step by step
        adapter = BatchSizeAdapter(initial_size=10, min_size=2, window_size=5)
        adapter.record_outcome(0.0) # 10 -> 6
        self.assertEqual(adapter.recommended_size(), 6)
        adapter.record_outcome(0.0) # 6 -> 4
        self.assertEqual(adapter.recommended_size(), 4)
        adapter.record_outcome(0.0) # 4 -> 2
        self.assertEqual(adapter.recommended_size(), 2)
        adapter.record_outcome(0.0) # 2 -> 2
        self.assertEqual(adapter.recommended_size(), 2)

    def test_window_sliding(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=2, window_size=3)
        adapter.record_outcome(1.0) # [T] rate 1.0
        adapter.record_outcome(1.0) # [T, T] rate 1.0
        adapter.record_outcome(0.0) # [T, T, F] rate 0.666
        self.assertAlmostEqual(adapter.success_rate(), 2/3)
        adapter.record_outcome(0.0) # [T, F, F] rate 0.333
        self.assertAlmostEqual(adapter.success_rate(), 1/3)
        self.assertLess(adapter.recommended_size(), 10)

    def test_success_rate_above_threshold(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=2, window_size=5)
        for _ in range(3):
            adapter.record_outcome(1.0) # rate 1.0
        self.assertEqual(adapter.recommended_size(), 10)

if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    import unittest
    unittest.main()
