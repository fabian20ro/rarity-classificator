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


if __name__ == "__main__":
    unittest.main()
