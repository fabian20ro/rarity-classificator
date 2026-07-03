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

    def test_max_size_none(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5, max_size=None)
        self.assertEqual(adapter.max_size, 10)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 10)

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

    def test_str(self):
        """__str__ returns a friendly single-line summary."""
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        s = str(adapter)
        self.assertIn("size=10", s)
        self.assertIn("trend=", s)
        self.assertIn("success_rate=", s)
        # After a failure: rate drops to 0%, trend changes.
        adapter.record_outcome(0.0)
        self.assertIn("rate=0%", str(adapter))

    def test_repr(self):
        """__repr__ includes all constructor parameters plus current state."""
        adapter = BatchSizeAdapter(
            initial_size=12, min_size=4, window_size=7, max_size=50,
        )
        r = repr(adapter)
        self.assertIn("size=12", r)
        self.assertIn("min=4", r)
        self.assertIn("max=50", r)

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

    def test_success_threshold_vs_adjustment_thresholds(self):
        """success_threshold decides binary outcome classification;
        low/high thresholds decide size adjustment — they are distinct."""
        # success_threshold=0.9: anything >=0.9 is a success record.
        # low_threshold=0.4, high_threshold=0.8: 0.5 -> stable (no adjust).
        adapter = BatchSizeAdapter(
            initial_size=10, min_size=3, window_size=2,
            success_threshold=0.9, low_threshold=0.4, high_threshold=0.8,
        )

        # record 0.5 -> classified as failure (0.5 < 0.9), but rate=0.0 < 0.4 -> decrease
        adapter.record_outcome(0.5)
        self.assertFalse(adapter.outcomes[-1])
        self.assertEqual(adapter.current_size, 6)  # max(3, 10*2//3)

    def test_reset_clears_all_state(self):
        """After reset() size and outcomes match a fresh instance."""
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        for _ in range(7):
            adapter.record_outcome(0.0)
        self.assertNotEqual(adapter.current_size, 10)

        adapter.reset()
        self.assertEqual(adapter.current_size, 10)
        self.assertEqual(len(adapter.outcomes), 0)
        # success_rate returns 1.0 when outcomes empty (existing contract);
        # trend reflects that default → "increasing" under default thresholds
        self.assertEqual(adapter.success_rate(), 1.0)

    def test_reset_preserves_config(self):
        """reset() must not alter constructor-set parameters."""
        adapter = BatchSizeAdapter(
            initial_size=10, min_size=5, window_size=8, max_size=30,
        )
        for _ in range(9):
            adapter.record_outcome(1.0)
        self.assertNotEqual(adapter.current_size, 10)

        adapter.reset()
        self.assertEqual(adapter.initial_size, 10)
        self.assertEqual(adapter.min_size, 5)
        self.assertEqual(adapter.window_size, 8)

    def test_window_eviction_clears_stale_successes(self):
        """After window overflow evicts old successes, success_rate reflects only recent history."""
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=2)

        # Record 2 successes to fill the window at default thresholds (low=0.5, high=0.9)
        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.success_rate(), 1.0)
        self.assertEqual(adapter.current_size, 10)

        # Overflow: record 2 failures — old successes evicted from window of size 2
        adapter.record_outcome(0.0)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.success_rate(), 0.0)
        # rate=0.0 < low_threshold=0.5 → decrease: max(3, 10*2//3) = 6
        self.assertEqual(adapter.current_size, 6)

    def test_is_converged_requires_stable_and_full_window(self):
        "is_converged is True only when trend=='stable' and window is full."
        # Default thresholds: low=0.5, high=0.9 — rate<0.5 → decreasing, >0.9 → increasing, else stable
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=4)
        self.assertFalse(adapter.is_converged)  # empty window

        # 4 failures: rate=0.0 < low → not converged
        for _ in range(4):
            adapter.record_outcome(0.0)
        self.assertEqual(adapter.trend, "decreasing")
        self.assertFalse(adapter.is_converged)

        # Reset; 4 successes: rate=1.0 > high → not converged
        adapter.reset()
        for _ in range(4):
            adapter.record_outcome(1.0)
        self.assertEqual(adapter.trend, "increasing")
        self.assertFalse(adapter.is_converged)

        # Mix 3 successes + 1 failure: rate=0.75 → stable but window full? Let's verify:
        # outcomes window_size=4 after 4 records → [T,T,T,F] → rate=0.75, trend="stable"
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=4)
        for _ in range(3):
            adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.trend, "stable")
        self.assertTrue(adapter.is_converged)

    def test_low_threshold_boundary_no_decrease(self):
        """rate == low_threshold → no decrease (strict < in _adjust_size)."""
        adapter = BatchSizeAdapter(
            initial_size=9, min_size=3, window_size=2,
            success_threshold=0.9, low_threshold=0.5, high_threshold=0.8,
        )
        # First record: rate=1.0 > 0.8 → increase to 13, capped at max_size=initial_size=9
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 9)
        # Second record (failure): window=[T,F], rate=0.5 == low_threshold → no adjust
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.success_rate(), 0.5)
        self.assertEqual(adapter.trend, "stable")
        self.assertEqual(adapter.current_size, 9)

    def test_high_threshold_boundary_no_increase(self):
        """rate == high_threshold → no increase (strict > in _adjust_size)."""
        adapter = BatchSizeAdapter(
            initial_size=12, min_size=3, window_size=4,
            success_threshold=0.9, low_threshold=0.4, high_threshold=0.75,
        )
        for _ in range(3):
            adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)
        # window: [T,T,T,F], rate=0.75 == high_threshold → no adjust
        self.assertEqual(adapter.success_rate(), 0.75)
        self.assertEqual(adapter.trend, "stable")
        self.assertEqual(adapter.current_size, 12)

    def test_extreme_success_threshold_zero(self):
        """success_threshold=0.0 classifies negative-normalized values as success."""
        adapter = BatchSizeAdapter(
            initial_size=10, min_size=3, window_size=2,
            success_threshold=0.0, low_threshold=0.4, high_threshold=0.8,
        )
        # -1.0 normalized to 0.0; >= 0.0 → True (success)
        adapter.record_outcome(-1.0)
        self.assertTrue(adapter.outcomes[-1])
        # 0.0 ≥ 0.0 → True (success); both successes in window: rate=1.0 > 0.8 → increase
        adapter.record_outcome(0.0)
        # Both successes → rate=1.0 > high_threshold=0.8 → increase to 15
        # but max_size defaults to initial_size=10 (max_size=None), so capped at 10
        self.assertEqual(adapter.current_size, 10)

    def test_extreme_success_threshold_one(self):
        """success_threshold=1.0 classifies only perfect outcomes as success."""
        adapter = BatchSizeAdapter(
            initial_size=10, min_size=3, window_size=2,
            success_threshold=1.0, low_threshold=0.4, high_threshold=0.8,
        )
        # 0.99 < 1.0 → classified as failure even though near-perfect
        adapter.record_outcome(0.99)
        self.assertFalse(adapter.outcomes[-1])
        # rate=0.0 < 0.4 → decrease: max(3, 10*2//3)=6
        self.assertEqual(adapter.current_size, 6)

    def test_adjustment_floor_math_progression(self):
        """Continuous adjustment must follow exact (x*2)//3 / (x*3)//2 math at every step."""
        # Decrease path: verify each floor-division step lands exactly where the formula says.
        adapter = BatchSizeAdapter(initial_size=10, min_size=1, window_size=2)
        expected_decrease = [6, 4, 2]  # (10*2)//3=6, (6*2)//3=4, (4*2)//3=2
        for expected in expected_decrease:
            adapter.record_outcome(0.0)
            self.assertEqual(adapter.current_size, expected)

        # Increase path with a small initial size so each step is observable.
        adapter = BatchSizeAdapter(initial_size=4, min_size=1, window_size=2, max_size=50)
        self.assertEqual(adapter.current_size, 4)
        # Two successes: rate=1.0 > high_threshold=0.9 → increase: (4*3)//2 = 6
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 6)
        # Third success: window=[T,T], rate=1.0 → increase: (6*3)//2 = 9
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 9)
        # Fourth success: window=[T,T], rate=1.0 → increase: (9*3)//2 = 13
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 13)

    def test_adjustment_min_cap_stops_decrease(self):
        """Decrease must stop at min_size and never go below it regardless of further failures."""
        adapter = BatchSizeAdapter(initial_size=4, min_size=2, window_size=2)
        # (4*2)//3 = 2 — reaches min_size exactly.
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 2)
        # Further failures must keep size at 2, not continue floor division to 1.
        for _ in range(5):
            adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 2)

    def test_adjustment_max_cap_stops_increase(self):
        """Increase must stop at max_size and never go above it regardless of further successes."""
        adapter = BatchSizeAdapter(initial_size=15, min_size=3, window_size=2, max_size=20)
        # Fill window with success to drive increase.
        for _ in range(4):
            adapter.record_outcome(1.0)
        # Current size should be capped at 20 even though (some value*3)//2 exceeds it.
        self.assertEqual(adapter.current_size, 20)
        # Further successes must keep size at 20.
        for _ in range(5):
            adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 20)

    def test_partial_window_adjustment_and_iteration(self):
        """_adjust_size fires on every record_outcome (partial windows); len/iter reflect deque."""
        adapter = BatchSizeAdapter(initial_size=9, min_size=1, window_size=5)
        # First outcome: rate=1.0 > 0.9 → increase: (9*3)//2 = 13; max defaults to initial=9 → capped at 9
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 9)
        self.assertEqual(len(adapter), 1)

        # Second outcome: rate=1.0 → increase: (9*3)//2 = 13; still capped at max=initial=9 → 9
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 9)
        self.assertEqual(len(adapter), 2)

        # Third outcome (failure): rate=2/3 ≈ 0.67 — stable under default thresholds → no adjust
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 9)
        self.assertEqual(len(adapter), 3)
        # Iteration yields same elements as deque
        self.assertEqual(list(iter(adapter)), list(adapter.outcomes))

        # Fourth outcome (failure): rate=2/4 = 0.5 == low_threshold → stable, no adjust
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 9)
        self.assertEqual(len(adapter), 4)

        # Fifth outcome (failure): rate=2/5 = 0.4 < 0.5 → decrease: max(1, (9*2)//3)=6
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 6)
        self.assertEqual(len(adapter), 5)

        # Sixth outcome pushes window past capacity — eviction happens too
        adapter.record_outcome(0.0)
        self.assertEqual(len(adapter), 5)  # still capped at window_size

    def test_success_ratio_clamp_boundary(self):
        """record_outcome clamps values outside [0,1] to the boundary before classification."""
        adapter = BatchSizeAdapter(
            initial_size=8, min_size=2, window_size=3,
            success_threshold=0.7, low_threshold=0.4, high_threshold=0.8,
        )
        # -5.0 normalized to 0.0 → below success_threshold=0.7 → failure
        adapter.record_outcome(-5.0)
        self.assertFalse(adapter.outcomes[-1])

        # 3.0 normalized to 1.0 → above success_threshold=0.7 → success
        adapter.record_outcome(3.0)
        self.assertTrue(adapter.outcomes[-1])

    def test_empty_window_first_record_triggers_increase(self):
        """A single record on empty outcomes yields rate=1.0 which exceeds high_threshold,
        triggering immediate size increase — verifying that _adjust_size fires before window is full."""
        adapter = BatchSizeAdapter(
            initial_size=6, min_size=2, window_size=5, max_size=30,
        )
        self.assertEqual(adapter.current_size, 6)
        # Empty outcomes: success_rate() returns 1.0 > high_threshold=0.9 → increase
        adapter.record_outcome(1.0)
        # (6*3)//2 = 9; capped at max_size=30 → 9
        self.assertEqual(adapter.current_size, 9)

    def test_alternating_outcomes_boundary_no_adjust(self):
        """Consecutive alternating outcomes that hover at threshold boundary trigger no adjustment."""
        # window_size=2; alternate S/F starting with success: [T,F] → rate=0.5 == low_threshold
        # Default thresholds: low=0.5, high=0.9 — 0.5 is NOT < 0.5, so no decrease.
        adapter = BatchSizeAdapter(initial_size=12, min_size=3, window_size=2)
        self.assertEqual(adapter.current_size, 12)
        # First success: rate=1.0 > 0.9 → increase capped at initial(12). Stays 12.
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 12)
        # Second (failure): window=[T,F], rate=0.5 == low_threshold → no adjust
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 12)
        # Third (success): window=[F,T], rate=0.5 == low_threshold → still stable
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 12)
        # Fourth (failure): window=[T,F], rate=0.5 → no adjust again
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 12)

    def test_get_metrics_reflects_converged_state(self):
        """get_metrics returns is_converged=True only when trend=='stable' AND window is full."""
        # Default thresholds: low=0.5, high=0.9 — stable at rate in [0.5, 0.9]
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=4)

        # Empty outcomes → success_rate()=1.0 > 0.9 → trend="increasing", not converged
        metrics = adapter.get_metrics()
        self.assertFalse(metrics["is_converged"])
        self.assertEqual(metrics["trend"], "increasing")
        self.assertEqual(metrics["window_usage"], 0)

        # Drive to full window with a stable mix: 3 successes + 1 failure → rate=0.75, stable
        for _ in range(3):
            adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)
        metrics = adapter.get_metrics()
        self.assertTrue(metrics["is_converged"])
        self.assertEqual(metrics["trend"], "stable")
        self.assertTrue(metrics["is_stable"])
        self.assertEqual(metrics["success_rate"], 0.75)
        self.assertEqual(metrics["window_usage"], 4)

        # After another record, window shifts: outcomes=[S,S,F,X] → partial (still full=4), but rate may shift to unstable
        adapter.record_outcome(0.0)
        metrics = adapter.get_metrics()
        # Window still full (size 4): [T,T,F,F] → rate=0.5 == low_threshold → stable, converged
        self.assertTrue(metrics["is_converged"])

    def test_get_metrics_reflects_partial_window_not_converged(self):
        """get_metrics must report is_converged=False when window is not full, even if trend is stable."""
        adapter = BatchSizeAdapter(
            initial_size=10, min_size=3, window_size=5,
            low_threshold=0.4, high_threshold=0.8,
        )
        # After 2 records at rate~1.0: trend="increasing" (not stable) but window partial → not converged
        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        metrics = adapter.get_metrics()
        self.assertFalse(metrics["is_converged"])

        # Drive to 5 records at rate=0.5 (stable under [0.4, 0.8]) but only partial window of size 3
        adapter.reset()
        for _ in range(2):
            adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)
        metrics = adapter.get_metrics()
        self.assertEqual(metrics["window_usage"], 3)
        # rate=2/3≈0.67 — stable under [0.4,0.8] → is_stable=True but NOT converged (window not full)
        self.assertTrue(metrics["is_stable"])
        self.assertFalse(metrics["is_converged"])

    def test_success_threshold_outside_adjustment_range_accepted(self):
        """success_threshold can sit outside [low, high] — they serve different purposes (binary classification vs rate-based adjustment)."""
        # success_threshold=0.95 is ABOVE high_threshold=0.8: outcomes >=0.95 classified as success;
        # but size adjusts based on window-rate vs 0.4/0.8. These are independent concerns.
        adapter = BatchSizeAdapter(
            initial_size=10, min_size=3, window_size=2,
            success_threshold=0.95, low_threshold=0.4, high_threshold=0.8,
        )

        # Outcome 0.96 → classified as success (>= 0.95) despite being below high_threshold=0.8 for adjustment
        adapter.record_outcome(0.96)
        self.assertTrue(adapter.outcomes[-1])

        # Window has one success: rate=1.0 > 0.8 → increase to 15 (capped at max_size=None → initial=10 wait — capped at max which is None so default to initial=10)
        # Actually max defaults to initial_size if None, so cap = 10; increase would be (10*3)//2=15 but capped at 10.
        self.assertEqual(adapter.current_size, 10)

        # Now record failure: window=[T,F], rate=0.5 — between low=0.4 and high=0.8 → stable, no adjust
        adapter.record_outcome(0.0)
        self.assertFalse(adapter.outcomes[-1])
        self.assertEqual(adapter.success_rate(), 0.5)
        self.assertEqual(adapter.trend, "stable")

    def test_consecutive_increases_stop_at_max(self):
        """Repeated successes must converge to max_size and hold there — increase chain terminates."""
        adapter = BatchSizeAdapter(
            initial_size=5, min_size=1, window_size=2, max_size=80,
        )
        # Drive up through several increases: 5→7→10→15→22→33→49→73 (next would be 109 but capped at 80)
        sizes = []
        for _ in range(20):
            adapter.record_outcome(1.0)
            sizes.append(adapter.current_size)

        self.assertEqual(sizes[-1], 80)
        # Verify the chain is monotonic and reaches cap
        for i in range(len(sizes) - 1):
            self.assertLessEqual(sizes[i], sizes[i + 1])
        self.assertEqual(adapter.trend, "increasing")

    def test_history_returns_plain_list(self):
        """history() returns a plain list copy of outcomes (newest last)."""
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=4)
        # Empty history before any record.
        self.assertEqual(adapter.history(), [])

        adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)
        h = adapter.history()
        self.assertEqual(h, [True, False])
        self.assertIsInstance(h, list)
        # Returned list is a copy — mutating it must not affect the adapter.
        h.append(True)
        self.assertNotEqual(adapter.outcomes[-1], True)  # deque still has 2 items

    def test_history_respects_window(self):
        """history() reflects current window contents after eviction."""
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=2)
        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)  # evicts first success → [True, False]
        self.assertEqual(adapter.history(), [True, False])

    def test_sparse_window_record_outcome_adjusts_on_empty_rate(self):
        """First record_outcome fires _adjust_size after appending the outcome,
        so success_rate() on the single-element window drives the first adjustment —
        verifying the append-before-adjust ordering."""
        adapter = BatchSizeAdapter(
            initial_size=6, min_size=2, window_size=3, max_size=40,
            success_threshold=0.7, low_threshold=0.5, high_threshold=0.8,
        )
        # First record: failure (0.0 < 0.7). outcome appended first → rate = 0/1 = 0.0 < 0.5 → decrease
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, max(2, (6 * 2) // 3))  # 4
        self.assertFalse(adapter.outcomes[-1])
        self.assertEqual(len(adapter.outcomes), 1)

        # Second record: success → rate = 1/2 = 0.5 == low_threshold → no adjust
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 4)
        self.assertTrue(adapter.outcomes[-1])

    def test_decrease_respects_min_cap_with_nondefault_thresholds(self):
        """_adjust_size must clamp to min_size via max(min_size, ...) even when
        custom low/high thresholds reshape the window-rate trend boundary."""
        adapter = BatchSizeAdapter(
            initial_size=6, min_size=4, window_size=2,
            success_threshold=0.9, low_threshold=0.3, high_threshold=0.7,
        )
        # Drive size down to exactly min_size via two consecutive failures:
        #   start=6, empty window → rate=1.0 > 0.7 → increase capped at max=initial=6 → stays 6
        adapter.record_outcome(0.0)  # outcomes=[F], rate=0.0 < 0.3 → decrease: max(4, (6*2)//3)=4
        self.assertEqual(adapter.current_size, 4)

        # Now at min_cap: further failures must NOT push size below min_size,
        # even though the raw floor-division formula would yield a smaller value.
        adapter.record_outcome(0.0)  # outcomes=[F,F], rate=0.0 < 0.3 → decrease: max(4, (4*2)//3)=max(4,2)=4
        self.assertEqual(adapter.current_size, 4)

        # Confirm the math path is hit — verify that without min cap, formula would differ.
        # Formula at size=4 with rate<low_threshold → (4*2)//3 = 2; capped to 4 by max(min_size, ...)
        # This exercises both the decrease branch and the min clamp in one flow under non-default thresholds.
        for _ in range(5):
            adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 4)

    def test_success_threshold_inside_adjustment_range(self):
        """When success_threshold sits between low_threshold and high_threshold,
        outcome classification (success_threshold) drives recording while size
        adjustment (low/high thresholds) drives _adjust_size — confirming they
        remain independent in this overlap configuration."""
        # success_threshold=0.5 classifies outcomes >= 0.5 as success;
        # low_threshold=0.3 / high_threshold=0.8 drive the window-rate trend band.
        adapter = BatchSizeAdapter(
            initial_size=10, min_size=3, window_size=4,
            success_threshold=0.5, low_threshold=0.3, high_threshold=0.8,
        )

        # --- Phase 1: build a stable mix inside [low, high] ---
        # Record 0.6 (≥ 0.5 → True) and 0.4 (< 0.5 → False).
        # After two records on empty window the first triggers an increase
        # (rate=1.0 > 0.8) capped at max_size=initial_size=10, so size stays 10.
        adapter.record_outcome(0.6)
        self.assertTrue(adapter.outcomes[-1])
        self.assertEqual(adapter.current_size, 10)

        # First failure: window=[T,F], rate=0.5 — between low=0.3 and high=0.8 → stable
        adapter.record_outcome(0.4)
        self.assertFalse(adapter.outcomes[-1])
        self.assertEqual(adapter.trend, "stable")
        self.assertEqual(adapter.current_size, 10)

        # --- Phase 2: push the window rate below low_threshold to trigger decrease ---
        # Record two more failures → window=[F,F] (evicts old successes since max window=4 but we only have 4 items total now),
        # rate = 0/4 = 0.0 < 0.3 → decrease: max(3, (10*2)//3) = 6.
        adapter.record_outcome(0.2)  # classified False (< 0.5)
        self.assertFalse(adapter.outcomes[-1])
        adapter.record_outcome(0.1)  # classified False
        self.assertFalse(adapter.outcomes[-1])

        # Window now has [T, F, F, F] → rate = 1/4 = 0.25 < 0.3 → decrease
        self.assertEqual(adapter.trend, "decreasing")
        self.assertEqual(adapter.current_size, max(3, (10 * 2) // 3))

    def test_step_count_increments_per_record(self):
        """Each record_outcome must increment step_count by exactly one."""
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        self.assertEqual(adapter.step_count, 0)
        for _ in range(7):
            adapter.record_outcome(1.0)
        self.assertEqual(adapter.step_count, 7)

    def test_step_count_resets_with_reset(self):
        """reset() must clear step_count alongside other state."""
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        for _ in range(8):
            adapter.record_outcome(1.0)
        self.assertEqual(adapter.step_count, 8)
        adapter.reset()
        self.assertEqual(adapter.step_count, 0)

    def test_step_count_in_metrics(self):
        """get_metrics must report the current step_count."""
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        for _ in range(4):
            adapter.record_outcome(1.0)
        metrics = adapter.get_metrics()
        self.assertEqual(metrics["step_count"], 4)

    def test_step_count_independent_of_window(self):
        """step_count must continue incrementing even after window eviction — it tracks total calls, not just visible outcomes."""
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=2)
        for _ in range(5):
            adapter.record_outcome(1.0)
        self.assertEqual(adapter.step_count, 5)
        self.assertEqual(len(adapter.outcomes), 2)

    def test_history_matches_window_content_and_order(self):
        """history() must return outcomes as a plain list preserving deque order."""
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=4)
        # Empty adapter: history is empty.
        self.assertEqual(adapter.history(), [])

        # Record mixed outcomes — oldest first (deque FIFO).
        adapter.record_outcome(1.0)   # True  -> [T]
        adapter.record_outcome(0.0)   # False -> [T,F]
        adapter.record_outcome(1.0)   # True  -> [T,F,T]
        expected = list(adapter.outcomes)
        self.assertEqual(adapter.history(), expected)

        # After window eviction (window_size=4, add two more failures):
        adapter.record_outcome(0.0)   # window=[T,F,T,F], len=4
        adapter.record_outcome(0.0)   # evicts first T -> [F,T,F,F]
        self.assertEqual(adapter.history(), list(adapter.outcomes))
        self.assertEqual(len(adapter.history()), 4)


if __name__ == "__main__":
    unittest.main()
