import unittest

from classificator.models import Step3MergeStrategy, UploadMode


class ModelsTest(unittest.TestCase):
    def test_upload_mode_parse_defaults_to_partial(self):
        self.assertIs(UploadMode.parse(None), UploadMode.PARTIAL)
        self.assertIs(UploadMode.parse(""), UploadMode.PARTIAL)
        self.assertIs(UploadMode.parse(" partial "), UploadMode.PARTIAL)

    def test_upload_mode_parse_accepts_full_fallback_alias(self):
        self.assertIs(UploadMode.parse("full-fallback"), UploadMode.FULL_FALLBACK)
        self.assertIs(UploadMode.parse("full_fallback"), UploadMode.FULL_FALLBACK)

    def test_upload_mode_parse_rejects_unknown_value(self):
        with self.assertRaises(ValueError):
            UploadMode.parse("unexpected")

    def test_step3_merge_strategy_parse_accepts_aliases(self):
        self.assertIs(Step3MergeStrategy.parse(None), Step3MergeStrategy.MEDIAN)
        self.assertIs(Step3MergeStrategy.parse("any-extremes"), Step3MergeStrategy.ANY_EXTREMES)
        self.assertIs(Step3MergeStrategy.parse("any_extremes"), Step3MergeStrategy.ANY_EXTREMES)
        self.assertIs(Step3MergeStrategy.parse("three-any-extremes"), Step3MergeStrategy.ANY_EXTREMES)
        self.assertIs(Step3MergeStrategy.parse("three_any_extremes"), Step3MergeStrategy.ANY_EXTREMES)

    def test_step3_merge_strategy_parse_rejects_unknown_value(self):
        with self.assertRaises(ValueError):
            Step3MergeStrategy.parse("unexpected")


if __name__ == "__main__":
    unittest.main()
