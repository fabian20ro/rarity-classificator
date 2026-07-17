from classificator.fuzzy_word_matcher import normalize, matches, levenshtein, MAX_EDIT_DISTANCE


def test_normalize():
    assert normalize("ăn") == "an"
    assert normalize("ĂN") == "an"
    assert normalize("ș") == "s"
    assert normalize("Ț") == "t"
    assert normalize("a") == "a"
    assert normalize("ĂNȚĂ") == "anta"
    assert normalize("ȘI") == "si"


def test_levenshtein_edge_cases():
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3
    assert levenshtein("abc", "ab") == 1
    assert levenshtein("abc", "axc") == 1
    assert levenshtein("abc", "ayz") == 2
    assert levenshtein("kitten", "sitting") == 3


def test_matches_exact():
    assert matches("apple", "apple") is True
    assert matches("APPLE", "apple") is True


def test_matches_diacritics():
    assert matches("ăn", "an") is True
    assert matches("ș", "s") is True
    assert matches("Ț", "t") is True
    assert matches("Ăntă", "anta") is True
    assert matches("ȘI", "si") is True


def test_matches_levenshtein_limit():
    # distance 1
    assert matches("cat", "can") is True
    # distance 2
    assert matches("cat", "caaa") is True
    # distance 3 (also length diff > MAX_EDIT_DISTANCE)
    assert matches("cat", "caaaaa") is False


def test_matches_length_diff_limit():
    """Length-diff short-circuit rejects when abs(len diff) exceeds MAX_EDIT_DISTANCE.

    Uses diacritic-only strings so the edit-distance path never fires:
    normalized forms are identical ('aa' vs 'b'), length diff = 2, which is == MAX_EDIT_DISTANCE (allowed).
    Then a true rejection case where length diff > MAX_EDIT_DISTANCE with no edit-distance ambiguity.
    """
    # abs(len('aa') - len('b')) == 1 <= MAX_EDIT_DISTANCE => not rejected by length check
    assert matches("ăă", "b") is True
    # abs(len('ăăă') - len('b')) == 2 == MAX_EDIT_DISTANCE => boundary, allowed
    assert matches("ăăă", "b") is True
    # abs(len('ăăăă') - len('b')) == 3 > MAX_EDIT_DISTANCE => short-circuit reject
    assert matches("ăăăă", "b") is False


def test_matches_normalize_then_length_reject():
    """Length-diff short-circuit fires even with diacritic normalization."""
    # "ăăăă" -> norm "aaaa"; "b" -> norm "b"; diff=3 > 2 → short-circuit reject
    assert matches("ăăăă", "b") is False
    # "țțțț" -> norm "tttt"; "x" -> norm "x"; diff=3 > 2 → short-circuit reject
    assert matches("țțțț", "x") is False


def test_matches_length_short_circuit():
    """Length-diff > MAX_EDIT_DISTANCE must reject regardless of content."""
    assert matches("aaaa", "b") is False
    assert matches("ab", "zzzzz") is False


def test_max_edit_distance_constant():
    """MAX_EDIT_DISTANCE must equal 2 — the threshold used by normalize and matches."""
    assert MAX_EDIT_DISTANCE == 2

if __name__ == "__main__":
    import unittest
    unittest.main()
