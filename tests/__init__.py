"""Tests for word-rarity-classifier"""
import unittest
from classificator.batch_size_adapter import BatchSizeAdapter

class TestPackageSmoke(unittest.TestCase):
    def test_batch_size_adapter_import(self):
        adapter = BatchSizeAdapter(10)
        self.assertEqual(adapter.current_size, 10)

    def test_batch_size_adapter_thresholds(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=1)
        adapter.record_outcome(0.9)  # Success (rate >= 0.9)
        self.assertEqual(adapter.current_size, 10)
        adapter.record_outcome(0.8)  # Failure (rate < 0.5)
        self.assertEqual(adapter.current_size, 6)
