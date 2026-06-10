import pytest
from src.classificator.fuzzy_word_matcher import normalize, matches, levenshtein, MAX_EDIT_DISTANCE

def test_normalize():
    assert normalize("ăn") == "an"
    assert normalize("ĂN") == "an"
    assert normalize("ș") == "s"
    assert normalize("Ț") == "t"
    assert normalize("a") == "a"

def test_levenshtein_edge_cases():
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3
    assert levenshtein("abc", "ab") == 1
    assert levenshtein("abc", "axc") == 1
    assert levenshtein("abc", "ayz") == 2

def test_matches_exact():
    assert matches("apple", "apple") is True
    assert matches("APPLE", "apple") is True

def test_matches_diacritics():
    assert matches("ăn", "an") is True
    assert matches("ș", "s") is True
    assert matches("Ț", "t") is True

def test_matches_levenshtein_limit():
    # distance 1
    assert matches("cat", "can") is True
    # distance 2
    assert matches("cat", "caaa") is True # 'cat' -> 'caa' (1) -> 'caaa' (2)? No.
    # Let's check: len(cat)=3, len(caaa)=4. diff=1.
    # cat vs caaa:
    # c-c, a-a, t-a (1) -> caa (dist 1) -> caaa (dist 2)
    # matches("cat", "caaa") -> diff=1 <= 2. True.
    # matches("cat", "caaaaa") -> diff=3 > 2. False.
    assert matches("cat", "caaaaa") is False

def test_matches_length_diff_limit():
    # abs(len(norm_expected) - len(norm_actual)) > MAX_EDIT_DISTANCE
    # MAX_EDIT_DISTANCE = 2
    # diff 3
    assert matches("cat", "caaaaa") is False

if __name__ == "__main__":
    import unittest
    unittest.main()
