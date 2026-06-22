import unittest
from src.classificator.batch_size_adapter import BatchSizeAdapter
from src.classificator.step2_metrics import Step2Metrics

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

    def test_step2_metrics_logic(self):
        metrics = Step2Metrics()
        metrics.record_batch_result(10, 10)
        metrics.record_batch_result(10, 5)
        self.assertEqual(metrics.total_batches, 2)
        self.assertEqual(metrics.total_scored, 15)
        self.assertEqual(metrics.total_failed, 5)
        self.assertEqual(metrics.successful_batches, 1)
        self.assertEqual(metrics.success_rate(), 0.5)

    def test_batch_size_adapter_thresholds(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        # Success threshold is 0.9
        adapter.record_outcome(0.9)
        self.assertTrue(adapter.outcomes[-1])
        adapter.record_outcome(0.89)
        self.assertFalse(adapter.outcomes[-1])
        adapter.record_outcome(1.1)
        self.assertTrue(adapter.outcomes[-1])
        adapter.record_outcome(-0.1)
        self.assertFalse(adapter.outcomes[-1])

    def test_batch_size_adapter_adjustment_down(self):
        adapter = BatchSizeAdapter(initial_size=15, min_size=3, window_size=2)
        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 10)

    def test_batch_size_adapter_adjustment_up(self):
        adapter = BatchSizeAdapter(initial_size=20, min_size=3, window_size=2)
        adapter.record_outcome(0.0)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 8)
        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 19)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 20)

    def test_categorize_error(self):
        from src.classificator.step2_metrics import categorize_error
        self.assertEqual(categorize_error("Missing content"), "MISSING_CONTENT")
        self.assertEqual(categorize_error("Unexpected end"), "TRUNCATED_JSON")
        self.assertEqual(categorize_error("Decimal error"), "DECIMAL_FORMAT")
        self.assertEqual(categorize_error("Word mismatch"), "WORD_MISMATCH")
        self.assertEqual(categorize_error("Model crash"), "MODEL_CRASH")
        self.assertEqual(categorize_error("Connection refused"), "CONNECTIVITY")
        self.assertEqual(categorize_error("Unknown"), "OTHER")
        self.assertEqual(categorize_error(None), "OTHER")

    def test_batch_size_adapter_edge_case_rates(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=10)
        # Rate = 0.5: 5 successes, 5 failures out of 10
        for _ in range(5):
            adapter.record_outcome(1.0)
        for _ in range(5):
            adapter.record_outcome(0.0)
        self.assertEqual(adapter.success_rate(), 0.5)
        self.assertEqual(adapter.current_size, 10)

        # Rate = 0.9: 9 successes, 1 failure out of 10
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=10)
        for _ in range(9):
            adapter.record_outcome(1.0)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.success_rate(), 0.9)
        self.assertEqual(adapter.current_size, 10)

        adapter.record_outcome(1.0)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 10)

    def test_batch_size_adapter_edge_case_rates_window_1(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=1)
        adapter.record_outcome(1.0)
        self.assertEqual(adapter.current_size, 10)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 10)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 6)
        adapter.record_outcome(0.0)
        self.assertEqual(adapter.current_size, 5)

    def test_step2_metrics_edge_case(self):
        metrics = Step2Metrics()
        self.assertEqual(metrics.total_batches, 0)
        self.assertEqual(metrics.total_scored, 0)
        self.assertEqual(metrics.total_failed, 0)
        self.assertEqual(metrics.successful_batches, 0)
        self.assertEqual(metrics.success_rate(), 1.0)

if __name__ == "__main__":
    unittest.main()
