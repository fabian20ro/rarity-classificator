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

if __name__ == "__main__":
    unittest.main()
