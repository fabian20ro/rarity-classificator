import unittest
from classificator.steps.step5_rebalance import _compute_adaptive_target_count

class TestStep5Logic(unittest.TestCase):
    def test_adaptive_target_count_zero_batch(self):
        result = _compute_adaptive_target_count(
            processed_before_batch=0,
            assigned_before_batch=0,
            batch_size=0,
            ratio=0.5,
            expected_total=10
        )
        self.assertEqual(result, 0)

    def test_adaptive_target_count_standard(self):
        # Scenario: 10 items in batch, ratio 0.5, expected 5.
        # after=10, desired=5, delta=5, result=5
        result = _compute_adaptive_target_count(
            processed_before_batch=0,
            assigned_before_batch=0,
            batch_size=10,
            ratio=0.5,
            expected_total=5
        )
        self.assertEqual(result, 5)

    def test_adaptive_target_count_overshoot_protection(self) :
        # Scenario: processed=5, assigned=4, batch=10, ratio=0.5, expected=10
        # processed_after=15, desired_cumulative=8, delta=4, result=4
        result = _compute_adaptive_target_count(
            processed_before_batch=5,
            assigned_before_batch=4,
            batch_size=10,
            ratio=0.5,
            expected_total=10
        )
        self.assertEqual(result, 4)

    def test_adaptive_target_count_cap_at_expected(self) :
        # Scenario: processed=0, assigned=0, batch=10, ratio=0.5, expected=2
        # processed_after=10, desired_cumulative=5, delta=5, cap=2 -> result=2
        result = _compute_adaptive_target_count(
            processed_before_batch=0,
            assigned_before_batch=0,
            batch_size=10,
            ratio=0.5,
            expected_total=2
        )
        self.assertEqual(result, 2)

    def test_adaptive_target_count_cap_at_batch_size(self) :
        # Scenario: processed=0, assigned=0, batch=1, ratio=0.5, expected=10
        # processed_after=1, desired_cumulative=1, delta=1, result=1
        result = _compute_adaptive_target_count(
            processed_before_batch=0,
            assigned_before_batch=0,
            batch_size=1,
            ratio=0.5,
            expected_total=10
        )
        self.assertEqual(result, 1)

    def test_rounding_precision(self):
        # Test the rounding behavior (int(x * ratio + 0.5))
        # processed_after = 1, ratio = 0.33, expected = 10
        # 1 * 0.33 + 0.5 = 0.83 -> 0
        # 1 * 0.66 + 0.5 = 1.16 -> 1
        # 1 * 0.5 + 0.5 = 1.0 -> 1
        
        # case 1
        result = _compute_adaptive_target_count(
            processed_before_batch=0,
            assigned_before_batch=0,
            batch_size=1,
            ratio=0.33,
            expected_total=10
        )
        self.assertEqual(result, 0)
        
        # case 2
        result = _compute_adaptive_target_count(
            processed_before_batch=0,
            assigned_before_batch=0,
            batch_size=1,
            ratio=0.66,
            expected_total=10
        )
        self.assertEqual(result, 1)

        # case 3
        result = _compute_adaptive_target_count(
            processed_before_batch=0,
            assigned_before_batch=0,
            batch_size=1,
            ratio=0.5,
            expected_total=10
        )
        self.assertEqual(result, 1)

if __name__ == "__main__":
    unittest.main()
