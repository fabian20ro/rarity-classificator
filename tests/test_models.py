import unittest

from classificator.models import (
    LmApiFlavor,
    LmModelConfig,
    ScoringOutputMode,
    Step3MergeStrategy,
    UploadMode,
)


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
        self.assertIs(
            Step3MergeStrategy.parse("any-extremes"),
            Step3MergeStrategy.ANY_EXTREMES,
        )
        self.assertIs(
            Step3MergeStrategy.parse("any_extremes"),
            Step3MergeStrategy.ANY_EXTREMES,
        )
        self.assertIs(
            Step3MergeStrategy.parse("three-any-extremes"),
            Step3MergeStrategy.ANY_EXTREMES,
        )
        self.assertIs(
            Step3MergeStrategy.parse("three_any_extremes"),
            Step3MergeStrategy.ANY_EXTREMES,
        )

    def test_step3_merge_strategy_parse_rejects_unknown_value(self):
        with self.assertRaises(ValueError):
            Step3MergeStrategy.parse("unexpected")

    def test_lm_model_config_reasoning_controls(self):
        assert (
            LmModelConfig(model_id="test", reasoning_effort="high").has_reasoning_controls()
            is True
        )
        assert LmModelConfig(model_id="test", enable_thinking=True).has_reasoning_controls() is True
        assert LmModelConfig(
            model_id="test", thinking_type="enabled"
        ).has_reasoning_controls() is True
        assert LmModelConfig(model_id="test").has_reasoning_controls() is False


class UploadModeEdgeTest(unittest.TestCase):
    """Negative-path and edge-case coverage for upload mode parsing."""

    def test_parse_none_and_empty_both_resolve_to_partial(self):
        self.assertIs(UploadMode.parse(None), UploadMode.PARTIAL)
        self.assertIs(UploadMode.parse(""), UploadMode.PARTIAL)

    def test_parse_case_insensitive(self):
        self.assertIs(UploadMode.parse("PARTIAL"), UploadMode.PARTIAL)
        self.assertIs(UploadMode.parse("FULL-FALLBACK"), UploadMode.FULL_FALLBACK)
        self.assertIs(UploadMode.parse("Full_Fallback"), UploadMode.FULL_FALLBACK)

    def test_parse_strips_whitespace(self):
        self.assertIs(UploadMode.parse("  partial  "), UploadMode.PARTIAL)
        self.assertIs(
            UploadMode.parse("  full-fallback  "),
            UploadMode.FULL_FALLBACK,
        )

    def test_rejects_garbage_values(self):
        for bad in ("0", "1", "random", "partial-", "full-fallback-extra"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    UploadMode.parse(bad)


class Step3MergeStrategyEdgeTest(unittest.TestCase):
    """Negative-path coverage for merge strategy parsing."""

    def test_rejects_garbage_values(self):
        for bad in ("0", "1", "random", "median-extra", "any-extremes-extra"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    Step3MergeStrategy.parse(bad)


class LmApiFlavorEnumTest(unittest.TestCase):
    """Confirm enum members and string values match the source-of-truth."""

    def test_members_and_values(self):
        self.assertEqual(LmApiFlavor.OPENAI_COMPAT.value, "openai_compat")
        self.assertEqual(LmApiFlavor.LMSTUDIO_REST.value, "lmstudio_rest")


class ScoringOutputModeEnumTest(unittest.TestCase):
    """Confirm enum members and string values match the source-of-truth."""

    def test_members_and_values(self):
        self.assertEqual(ScoringOutputMode.SCORE_RESULTS.value, "score_results")
        self.assertEqual(
            ScoringOutputMode.SELECTED_WORD_IDS.value, "selected_word_ids"
        )


if __name__ == "__main__":
    unittest.main()
