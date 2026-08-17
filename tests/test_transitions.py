import unittest
from classificator.transitions import (
    LevelTransition,
    parse_transitions,
    require_valid_pair_transition,
    require_valid_transition,
    validate_transition_set,
)


class TransitionsTest(unittest.TestCase):
    def test_parse_transitions_single_and_pair(self):
        parsed = parse_transitions("2:1,3-4:3")
        self.assertEqual(
            parsed,
            [
                LevelTransition(from_level=2, to_level=1, from_level_upper=None),
                LevelTransition(from_level=3, to_level=3, from_level_upper=4),
            ],
        )

    def test_validate_transition_overlap_fails(self):
        transitions = [
            LevelTransition(from_level=2, to_level=1),
            LevelTransition(from_level=2, to_level=2),
        ]
        with self.assertRaises(ValueError):
            validate_transition_set(transitions)

    def test_require_valid_transition_edge_cases(self):
        # Valid
        require_valid_transition(3, 2)
        require_valid_transition(2, 2)
        require_valid_pair_transition(2, 3, 2)
        require_valid_pair_transition(2, 3, 3)

        # Invalid range
        with self.assertRaises(ValueError):
            require_valid_transition(0, 1)
        with self.assertRaises(ValueError):
            require_valid_transition(6, 5)

        # Invalid relation
        with self.assertRaises(ValueError):
            require_valid_transition(1, 3)
        with self.assertRaises(ValueError):
            require_valid_transition(2, 3)

        # 5:5 forbidden
        with self.assertRaises(ValueError):
            require_valid_transition(5, 5)

    def test_parse_transitions_duplicates(self):
        # If duplicates are provided, it should now raise ValueError.
        with self.assertRaises(ValueError):
            parse_transitions("2:1, 2:1")

    def test_parse_transitions_overlap_fails(self):
        # If transitions overlap source levels (e.g. single and pair), it should raise ValueError.
        with self.assertRaises(ValueError):
            parse_transitions("1:1, 1-2:2")

    def test_require_valid_pair_transition_failures(self):
        # Invalid range
        with self.assertRaises(ValueError):
            require_valid_pair_transition(0, 1, 1)
        with self.assertRaises(ValueError):
            require_valid_pair_transition(6, 7, 6)

        # Non-consecutive
        with self.assertRaises(ValueError):
            require_valid_pair_transition(1, 3, 1)

        # Target not in source
        with self.assertRaises(ValueError):
            require_valid_pair_transition(1, 2, 3)

    def test_validate_transition_set_empty_fails(self):
        with self.assertRaises(ValueError):
            validate_transition_set([])

    # -- LevelTransition utility methods -----------------------------------

    def test_describe_sources_single(self):
        t = LevelTransition(from_level=3, to_level=2)
        self.assertEqual(t.describe_sources(), "3")

    def test_describe_sources_pair(self):
        t = LevelTransition(from_level=3, from_level_upper=4, to_level=3)
        self.assertEqual(t.describe_sources(), "3-4")

    def test_other_level_downgrade(self):
        # 3:2 downgrade → other is the source level (from_level != to_level).
        t = LevelTransition(from_level=3, to_level=2)
        self.assertEqual(t.other_level(), 3)

    def test_other_level_same_level(self):
        # Same-level transition returns min(5, to_level + 1).
        t = LevelTransition(from_level=4, to_level=4)
        self.assertEqual(t.other_level(), 5)

    def test_other_level_pair_target_lower(self):
        # Pair 2-3→2: source_levels=[2,3], target is 2 → other is 3.
        t = LevelTransition(from_level=2, from_level_upper=3, to_level=2)
        self.assertEqual(t.other_level(), 3)

    def test_other_level_pair_target_upper(self):
        # Pair 2-3→3: source_levels=[2,3], target is 3 → other is 2.
        t = LevelTransition(from_level=2, from_level_upper=3, to_level=3)
        self.assertEqual(t.other_level(), 2)

    def test_source_levels_single(self):
        t = LevelTransition(from_level=4, to_level=3)
        self.assertEqual(t.source_levels(), [4])

    def test_source_levels_pair(self):
        t = LevelTransition(from_level=3, from_level_upper=4, to_level=3)
        self.assertEqual(t.source_levels(), [3, 4])

    def test_parse_transitions_duplicates_rejected(self):
        # Duplicates are caught by validate_transition_set before dedup runs.
        with self.assertRaises(ValueError):
            parse_transitions("3:2, 3:2, 4:3")

    def test_parse_transitions_sort_order(self):
        # Verify ordering by (from_level, from_level_upper or from_level, to_level).
        parsed = parse_transitions("5:4, 3-4:3, 1:1")
        self.assertEqual(
            [(t.from_level, t.to_level) for t in parsed],
            [(1, 1), (3, 3), (5, 4)],
        )

    def test_parse_transitions_single_dedup(self):
        # Single token with no duplicates: parse → validate passes → dedup dict
        # preserves it. Order is deterministic.
        parsed = parse_transitions("4:3")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].from_level, 4)
        self.assertEqual(parsed[0].to_level, 3)

    def test_other_level_same_level_at_lower_boundary(self):
        # Same-level at level 1 should return min(5, 2) = 2 — the upward candidate.
        t = LevelTransition(from_level=1, to_level=1)
        self.assertEqual(t.other_level(), 2)

    def test_other_level_same_level_at_cap(self):
        # Same-level at level 4 returns 5 (capped); level 3 returns 4; etc.
        for from_ in range(1, 5):
            t = LevelTransition(from_level=from_, to_level=from_)
            expected = min(5, from_ + 1)
            self.assertEqual(t.other_level(), expected)

    def test_parse_transitions_whitespace_only_uses_default(self):
        # raw="" is falsy → falls back to DEFAULT_REBALANCE_TRANSITIONS.
        parsed = parse_transitions("")
        self.assertGreater(len(parsed), 0)

    def test_parse_transitions_empty_after_strip_raises(self):
        # " " strips to "" then splits to [""] which fails the from:to check.
        with self.assertRaises(ValueError):
            parse_transitions(" ")

    def test_parse_transitions_negative_number_rejected(self):
        # Negative integers should be rejected at int-parse time or by validation.
        with self.assertRaises(ValueError):
            parse_transitions("-1:0")

    def test_other_level_same_level_at_5(self):
        # Same-level at level 5 returns 5 (already at cap).
        t = LevelTransition(from_level=5, to_level=5)
        self.assertEqual(t.other_level(), 5)

    def test_pair_transition_from_4_to_5_target_upper(self):
        # Pair 4-5→5: source_levels=[4,5], target is 5 → other is 4.
        t = LevelTransition(from_level=4, from_level_upper=5, to_level=5)
        self.assertEqual(t.other_level(), 4)

    def test_pair_transition_from_3_to_5_target_lower(self):
        # Pair 3-4→3: source_levels=[3,4], target is 3 → other is 4.
        t = LevelTransition(from_level=3, from_level_upper=4, to_level=3)
        self.assertEqual(t.other_level(), 4)

    def test_require_valid_pair_transition_out_of_range_target(self):
        # Target outside 1..5 is invalid even if sources are valid.
        with self.assertRaises(ValueError):
            require_valid_pair_transition(2, 3, 6)
        with self.assertRaises(ValueError):
            require_valid_pair_transition(2, 3, 0)

    def test_require_valid_pair_transition_source_range(self):
        # Source levels outside 1..5 are invalid.
        with self.assertRaises(ValueError):
            require_valid_pair_transition(-1, 0, 1)

if __name__ == "__main__":
    unittest.main()
