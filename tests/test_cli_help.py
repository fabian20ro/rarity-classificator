import argparse
import unittest

from classificator.cli import _build_parser


class CliHelpTest(unittest.TestCase):
    def test_step4_help_mentions_upload_mode_aliases(self):
        parser = _build_parser()
        subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        help_text = subparsers.choices["step4-upload"].format_help()
        self.assertIn("Upload mode (default: partial; accepts full-", help_text)
        self.assertIn("fallback/full_fallback)", help_text)

    def test_step4_alias_help_mentions_partial_default(self):
        parser = _build_parser()
        subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        help_text = subparsers.choices["step4"].format_help()
        self.assertIn("Alias of step4-upload", help_text)
        self.assertIn("default: partial", help_text)
        self.assertIn("full-fallback/full_fallback", help_text)

    def test_step5_help_mentions_exact_count_local_id_contract(self):
        help_text = _build_parser().format_help()
        self.assertIn("Rebalance levels with strict batch-local local_id", help_text)
        self.assertIn("selection (exact-count 1..N", help_text)
        self.assertIn("unique, no 0, no word-id", help_text)
        self.assertIn("fallback)", help_text)

    def test_review_help_mentions_include_undecided(self):
        parser = _build_parser()
        subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        help_text = subparsers.choices["review-low-confidence"].format_help()
        alias_help_text = subparsers.choices["review"].format_help()
        self.assertIn("Interactive review of lowest-confidence words", help_text)
        self.assertIn("--include-undecided", help_text)
        self.assertIn("Alias of review-low-confidence", alias_help_text)
        self.assertIn("--include-undecided", alias_help_text)

    def test_step5_help_mentions_dry_run(self):
        parser = _build_parser()
        subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        help_text = subparsers.choices["step5-rebalance"].format_help()
        alias_help_text = subparsers.choices["step5"].format_help()
        self.assertIn("--dry-run", help_text)
        self.assertIn("Simulate the run without writing", help_text)
        self.assertIn("--dry-run", alias_help_text)


class AllSubcommandHelpTest(unittest.TestCase):
    def test_all_subcommands_have_non_empty_help(self):
        parser = _build_parser()
        subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        missing = []
        for name, cmd_parser in sorted(subparsers.choices.items()):
            help_text = cmd_parser.format_help().strip()
            if not help_text:
                missing.append(name)
        self.assertEqual(missing, [], f"subcommands with empty help text: {missing}")


if __name__ == "__main__":
    unittest.main()
