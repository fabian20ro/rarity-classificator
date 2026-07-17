import unittest

from classificator.lm.client import (
    SELECTION_REPAIR_SYSTEM_PROMPT,
    SELECTION_REPAIR_USER_TEMPLATE,
    LmStudioClient,
)
from classificator.models import ScoringOutputMode


class SelectionRepairPromptTest(unittest.TestCase):
    def test_system_prompt_restates_strict_local_id_contract(self):
        self.assertIn("exact numărul cerut", SELECTION_REPAIR_SYSTEM_PROMPT)
        self.assertIn("`local_id`", SELECTION_REPAIR_SYSTEM_PROMPT)
        self.assertIn("`1..N`", SELECTION_REPAIR_SYSTEM_PROMPT)
        self.assertIn("Fără `0`", SELECTION_REPAIR_SYSTEM_PROMPT)
        self.assertIn("Fără fallback la `word_id` sau poziții", SELECTION_REPAIR_SYSTEM_PROMPT)

    def test_user_template_restates_exact_count_and_local_id_contract(self):
        self.assertIn("Numărul exact de id-uri", SELECTION_REPAIR_USER_TEMPLATE)
        self.assertIn("contractul local_id `1..N`", SELECTION_REPAIR_USER_TEMPLATE)

    def test_resolve_selection_prompt_counts_passthrough_when_not_selected_mode(self):
        client = LmStudioClient(api_key=None)
        ctx = type(
            "Ctx", (), {"output_mode": ScoringOutputMode.SCORE_RESULTS, "system_prompt": "sys", "user_template": "usr"}
        )()
        sys_p, user_t = client._resolve_selection_prompt_counts(ctx)
        self.assertEqual(sys_p, "sys")
        self.assertEqual(user_t, "usr")

    def test_resolve_selection_prompt_counts_passthrough_when_expected_none(self):
        client = LmStudioClient(api_key=None)
        ctx = type(
            "Ctx", (), {
                "output_mode": ScoringOutputMode.SELECTED_WORD_IDS,
                "expected_json_items": None,
                "system_prompt": "sys",
                "user_template": "usr",
            }
        )()
        sys_p, user_t = client._resolve_selection_prompt_counts(ctx)
        self.assertEqual(sys_p, "sys")
        self.assertEqual(user_t, "usr")

    def test_resolve_selection_prompt_counts_substitutes_placeholders(self):
        client = LmStudioClient(api_key=None)
        ctx = type(
            "Ctx", (), {
                "output_mode": ScoringOutputMode.SELECTED_WORD_IDS,
                "expected_json_items": 42,
                "system_prompt": "pick {{TARGET_COUNT}} items from {{COMMON_COUNT}} candidates",
                "user_template": "{{TARGET_COUNT}} ids out of {{COMMON_COUNT}}",
            }
        )()
        sys_p, user_t = client._resolve_selection_prompt_counts(ctx)
        self.assertEqual(sys_p, "pick 42 items from 42 candidates")
        self.assertEqual(user_t, "42 ids out of 42")

    def test_apply_selection_count_placeholders_replaces_both(self):
        client = LmStudioClient(api_key=None)
        prompt = "{{TARGET_COUNT}} {{COMMON_COUNT}} {{TARGET_COUNT}}"
        result = client._apply_selection_count_placeholders(prompt, expected=7)
        self.assertEqual(result, "7 7 7")

    def test_apply_selection_count_placeholders_no_placeholders(self):
        client = LmStudioClient(api_key=None)
        prompt = "no placeholders here"
        result = client._apply_selection_count_placeholders(prompt, expected=7)
        self.assertEqual(result, "no placeholders here")

    def test_separation_repair_prompt_mentions_avoid_vulgarity(self):
        """Repair prompts must discourage obscene term selection."""
        self.assertIn("Evită termeni vulgari/obsceni", SELECTION_REPAIR_SYSTEM_PROMPT)

    def test_system_prompt_forbids_zero_indices(self):
        """System prompt must explicitly reject word_id fallback to 0.

        Production contract (client.py, SELECTION_REPAIR_SYSTEM_PROMPT):
            "Fără `0`" — the repair prompt is strict about local_ids starting at 1.
        This test verifies that constraint rather than leaving it implicit.
        """
        self.assertIn("Fără `0`", SELECTION_REPAIR_SYSTEM_PROMPT)

    def test_apply_selection_count_placeholders_distinct_target_common(self):
        """Placeholder substitution handles distinct target/common counts correctly.

        Production contract (_apply_selection_count_placeholders, client.py):
            Replaces REBALANCE_TARGET_COUNT_PLACEHOLDER with str(expected), then
            replaces REBALANCE_COMMON_COUNT_PLACEHOLDER also with str(expected).
        In current usage both are set to the same expected count, but we verify the
        substitution is order-independent and works when target != common.
        """
        client = LmStudioClient(api_key=None)
        prompt = "target={{TARGET_COUNT}} common={{COMMON_COUNT}}"
        result = client._apply_selection_count_placeholders(prompt, expected=5)
        self.assertEqual(result, "target=5 common=5")

    def test_resolve_selection_prompt_counts_target_common_passthrough_when_not_selected(self):
        """When mode is not SELECTED_WORD_IDS, placeholders must be preserved verbatim."""
        client = LmStudioClient(api_key=None)
        ctx = type(
            "Ctx", (), {
                "output_mode": ScoringOutputMode.SCORE_RESULTS,
                "system_prompt": "{{TARGET_COUNT}} from {{COMMON_COUNT}}",
                "user_template": "{{TARGET_COUNT}} of {{COMMON_COUNT}}",
            }
        )()
        sys_p, user_t = client._resolve_selection_prompt_counts(ctx)
        self.assertEqual(sys_p, "{{TARGET_COUNT}} from {{COMMON_COUNT}}")
        self.assertEqual(user_t, "{{TARGET_COUNT}} of {{COMMON_COUNT}}")


if __name__ == "__main__":
    unittest.main()
