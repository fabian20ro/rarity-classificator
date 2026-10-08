"""Normalized full edit distance, not prefix similarity, decides fuzzy matches."""
import pytest

from classificator.fuzzy_word_matcher import (
    normalize, matches, levenshtein, MAX_EDIT_DISTANCE, matches_with_distance,
)


@pytest.mark.parametrize("text,expected", [
    ("", ""), ("ăn", "an"), ("ĂN", "an"), ("ș", "s"), ("Ț", "t"),
    ("ĂNȚĂ", "anta"), ("ȘI", "si"), ("Î", "i"), ("înțeles", "inteles"),
])
def test_normalize(text, expected):
    assert normalize(text) == expected
    assert normalize(normalize(text)) == expected


def test_normalize_expands_compatibility_ligature_via_nfkd():
    # NFKD compatibility decomposition maps the fi-ligature to its two
    # letters ("fi"); canonical diacritic rows only strip a combining mark.
    # Swapping the source's deliberate NFKD for NFD leaves every canonical
    # diacritic row green but yields "" here, so this row pins the form.
    assert normalize("\ufb01") == "fi"
    assert normalize(normalize("\ufb01")) == "fi"


@pytest.mark.parametrize("left,right,distance", [
    ("abc", "abc", 0), ("", "abc", 3), ("abc", "ab", 1),
    ("abc", "axc", 1), ("abc", "ayz", 2), ("kitten", "sitting", 3),
    ("aab", "ab", 1),
])
def test_levenshtein(left, right, distance):
    assert levenshtein(left, right) == distance
    assert levenshtein(right, left) == distance


@pytest.mark.parametrize("left,right,distance", [
    ("apple", "apple", 0), ("APPLE", "apple", 0),
    ("ăn", "an", 0), ("ș", "s", 0), ("Ț", "t", 0), ("Ăntă", "anta", 0),
    ("cat", "can", 1), ("cat", "cut", 1), ("cat", "caaa", 2),
    ("cat", "caaaaa", 4), ("kitten", "sitting", 3),
    ("ăă", "b", 2), ("ăăă", "b", 3), ("ăăăă", "b", 4), ("țțțț", "x", 4),
    ("ab", "zzzzz", 5), ("", "", 0), ("", "a", 1), ("", "ab", 2),
    ("", "abc", 3), ("", "abcde", 5), ("a", "a", 0), ("a", "b", 1),
    ("abc", "d", 3), ("cat", "cax", 1), ("test", "text", 1),
    ("abcde", "abxde", 1), ("ab", "ac", 1), ("xy", "xz", 1),
    # Two substitutions are two edits, even with no character overlap.
    ("ab", "cd", 2), ("cd", "ef", 2), ("cat", "xyz", 3),
    ("băt", "bat", 0), ("abc", "abd", 1), ("ăa", "aa", 0),
    ("ă", "a", 0), ("înțeles", "inteles", 0), ("ȘI", "si", 0),
])
def test_matches_complete_distance(left, right, distance):
    assert MAX_EDIT_DISTANCE == 2
    for expected, actual in [(left, right), (right, left)]:
        assert matches_with_distance(expected, actual) == (distance <= 2, distance)
        assert matches(expected, actual) is (distance <= 2)


def test_matches_rejects_word_which_is_only_prefix_not_full_distance_match():
    # "cat" is a true prefix of "category", but full distance is 5 (> 2),
    # so a prefix-only similarity heuristic would wrongly accept this pair.
    assert matches_with_distance("cat", "category") == (False, 5)
    assert matches_with_distance("category", "cat") == (False, 5)
    assert matches("cat", "category") is False
    assert matches("category", "cat") is False
