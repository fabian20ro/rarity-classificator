import unittest

from classificator.lm.client import SELECTION_REPAIR_SYSTEM_PROMPT, SELECTION_REPAIR_USER_TEMPLATE


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


if __name__ == "__main__":
    unittest.main()
