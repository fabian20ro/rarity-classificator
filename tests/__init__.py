"""Tests for word-rarity-classifier"""
import unittest
from classificator.batch_size_adapter import BatchSizeAdapter

class TestPackageSmoke(unittest.TestCase):
    def test_batch_size_adapter_import(self):
        adapter = BatchSizeAdapter(10)
        self.assertEqual(adapter.current_size, 10)
