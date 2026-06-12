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
            
    def test_parse_transitions_invalid_format(self):
        with self.assertRaises(ValueError):
            parse_transitions("2-1") # missing :
        with self.assertRaises(ValueError):
            parse_transitions("2:3") # invalid relation (upgrade)
        with self.assertRaises(ValueError):
            parse_transitions("5:5") # 5:5 forbidden

if __name__ == "__main__":
    unittest.main()
