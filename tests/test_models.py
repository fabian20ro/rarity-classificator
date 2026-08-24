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
        with self.assertRaises(ValueError) as err:
            UploadMode.parse("unexpected")
        self.assertIn("uploadmode", str(err.exception).lower())
        self.assertIn("unexpected", str(err.exception))

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
        with self.assertRaises(ValueError) as err:
            Step3MergeStrategy.parse("unexpected")
        self.assertIn("step3mergestrategy", str(err.exception).lower())
        self.assertIn("unexpected", str(err.exception))

    def test_malformed_alias_target_raises_value_error(self):
        """A misspelled alias target (one that doesn't exist on the class) must raise ValueError, not AttributeError.

        Parametrized across every real enum in models.py to make the guard deterministic, then verified
        against a FakeStrategy covering the same path as the original single-test history.
        """
        import classificator.models as models_mod

        _malicious_map = {
            "ANY-EXTREMES": "VALID_ALIAS",
            "MALFORMED_ALIAS": "MISSPELLED_NAME",
        }

        for enum_cls in (UploadMode, Step3MergeStrategy, ScoringOutputMode):
            with self.subTest(enum=enum_cls.__name__):
                with self.assertRaises(ValueError) as err:
                    models_mod._parse_value_to_enum(
                        enum_cls, "MALFORMED_ALIAS", "PARTIAL", _malicious_map
                    )
                exc_str = str(err.exception).lower()
                self.assertIn("alias target", exc_str)
                self.assertIn(enum_cls.__name__.lower(), exc_str)

        class FakeStrategy:
            MEDIAN = "MEDIAN"
            ANY_EXTREMES = "ANY_EXTREMES"

        fake_alias_map = {
            "ANY-EXTREMES": "ANY_EXTREMES",
            "THREE_ANY_EXTREMES": "MISSPELLED_NAME",
        }
        with self.assertRaises(ValueError) as err:
            models_mod._parse_value_to_enum(FakeStrategy, "three_any_extremes", "MEDIAN", fake_alias_map)
        self.assertIn("alias target", str(err.exception).lower())

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
                with self.assertRaises(ValueError) as err:
                    UploadMode.parse(bad)
                message = str(err.exception)
                self.assertIn("invalid uploadmode value", message.lower())
                self.assertIn(bad, message)


class Step3MergeStrategyEdgeTest(unittest.TestCase):
    """Negative-path coverage for merge strategy parsing."""

    def test_rejects_garbage_values(self):
        for bad in ("0", "1", "random", "median-extra", "any-extremes-extra"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    Step3MergeStrategy.parse(bad)


class ScoringOutputModeEdgeTest(unittest.TestCase):
    """Negative-path coverage for scoring output mode parsing."""

    def test_rejects_garbage_values(self):
        for bad in ("0", "1", "random", "score_results-extra", "selected_word_ids-extra"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    ScoringOutputMode.parse(bad)


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

    def test_parse_defaults_to_score_results(self):
        self.assertIs(ScoringOutputMode.parse(None), ScoringOutputMode.SCORE_RESULTS)
        self.assertIs(ScoringOutputMode.parse(""), ScoringOutputMode.SCORE_RESULTS)
        self.assertIs(ScoringOutputMode.parse(" score_results "), ScoringOutputMode.SCORE_RESULTS)

    def test_parse_accepts_selected_word_ids(self):
        self.assertIs(
            ScoringOutputMode.parse("selected_word_ids"),
            ScoringOutputMode.SELECTED_WORD_IDS,
        )

    def test_parse_case_insensitive_and_strips_whitespace(self):
        self.assertIs(ScoringOutputMode.parse("SCORE_RESULTS"), ScoringOutputMode.SCORE_RESULTS)
        self.assertIs(
            ScoringOutputMode.parse(" Selected_Word_Ids "),
            ScoringOutputMode.SELECTED_WORD_IDS,
        )

    def test_parse_rejects_unknown_value(self):
        with self.assertRaises(ValueError) as err:
            ScoringOutputMode.parse("unexpected")
        self.assertIn("scoringoutputmode", str(err.exception).lower())
        self.assertIn("unexpected", str(err.exception))


if __name__ == "__main__":
    unittest.main()
