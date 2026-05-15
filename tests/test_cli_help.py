import unittest

from classificator.cli import _build_parser


class CliHelpTest(unittest.TestCase):
    def test_step5_help_mentions_exact_count_local_id_contract(self):
        help_text = _build_parser().format_help()
        self.assertIn("Rebalance levels with strict batch-local local_id", help_text)
        self.assertIn("selection (exact-count 1..N", help_text)
        self.assertIn("unique, no 0, no word-id", help_text)
        self.assertIn("fallback)", help_text)


if __name__ == "__main__":
    unittest.main()
