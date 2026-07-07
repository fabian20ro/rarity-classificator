import unittest
from classificator.batch_size_adapter import BatchSizeAdapter

class TestPackageIntegrity(unittest.TestCase):
    def test_batch_size_adapter_import(self):
        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        self.assertEqual(adapter.current_size, 10)
    unittest.main()
