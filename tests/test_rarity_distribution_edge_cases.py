import unittest
from src.classificator.distribution import RarityDistribution

class TestRarityDistributionEdgeCases(unittest.TestCase):
    def test_invalid_increment_levels(self):
        d = RarityDistribution()
        with self.assertRaises(ValueError):
            d.increment(0)
        with self.assertRaises(ValueError):
            d.increment(6)
        with self.assertRaises(ValueError):
            d.increment(-1)

    def test_invalid_set_level_levels(self) -> None:
        d = RarityDistribution()
        with self.assertRaises(ValueError):
            d.set_level(None, 6)
        with self.assertRaises(ValueError):
            d.set_level(3, 0)

    def test_invalid_count_levels(self) -> None:
        d = RarityDistribution()
        with self.assertRaises(ValueError):
            d.count(0)
        with self.assertRaises(ValueError):
            d.count(6)

    def test_total_zero(self) -> None:
        d = RarityDistribution()
        self.assertEqual(d.total, 0)
        self.assertEqual(d.format(), "distribution=[1:0(0.0%) 2:0(0.0%) 3:0(0.0%) 4:0(0.0%) 5:0(0.0%)]")

if __name__ == '__main__':
    unittest.main()
