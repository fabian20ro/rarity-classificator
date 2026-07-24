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


def test_normalize_empty_and_single_char():
    """normalize must handle empty string and single characters deterministically."""
    assert normalize("") == ""
    assert normalize("ă") == "a"
    assert normalize("Î") == "i"
    # round-trip: diacritic char -> normalized -> lowercase is idempotent
    assert normalize(normalize("Ăn")) == normalize("Ăn")


def test_matches_empty_strings():
    """matches must behave deterministically for empty-string inputs."""
    assert matches("", "") is True  # levenshtein("", "") == 0
    assert matches("a", "") is True  # len diff=1, edit dist=1 <= MAX_EDIT_DISTANCE
    assert matches("", "ab") is True  # len diff=2, edit dist=2 <= MAX_EDIT_DISTANCE
    assert matches("", "abc") is False  # len diff=3 > MAX_EDIT_DISTANCE → short-circuit


def test_matches_single_char_edge():
    """Single-char comparison: exact + one-edit-distance determinism."""
    assert matches("a", "a") is True  # exact after normalization
    assert matches("ă", "a") is True  # diacritic fold to same normalized form
    assert matches("abc", "d") is False  # len diff=2 OK, but edit dist > 2


def test_matches_prefix_short_circuit():
    """Common-prefix short-circuit: ≤1 mismatch in first 3 chars AND len diff ≤1 → accept."""
    # "cat" vs "cax": 2/3 prefix match, same length → accept via prefix short-circuit
    assert matches("cat", "cax") is True
    # "test" vs "text": 2/4 prefix match (t,e match), len diff=0 → accept
    assert matches("test", "text") is True
    # "abcde" vs "abxde": 2/5 prefix match, len diff=0 → accept
    assert matches("abcde", "abxde") is True


def test_matches_short_string_overlap():
    """Short strings (≤2 chars) with any character overlap should be accepted.

    This provides deterministic signal for very short words where edit distance alone
    may not reliably distinguish noise from real near-matches.
    """
    # "ab" vs "ac": share 'a' → accept via short-string overlap path
    assert matches("ab", "ac") is True
    # "xy" vs "xz": share 'x' → accept
    assert matches("xy", "xz") is True
    # "ab" vs "cd": no overlap, len ≤2 but empty intersection → reject (edit dist=2 boundary)
    assert matches("ab", "cd") is False


def test_matches_prefix_short_circuit_reject():
    """Prefix short-circuit must NOT accept when prefix match is insufficient or length diff > 1."""
    # "cat" vs "xyz": 0/3 prefix match → prefix check fails, edit dist=3 > 2 → reject
    assert matches("cat", "xyz") is False
    # "abcde" vs "abxyz": 2/5 prefix match but len diff=0; common_prefix < 3-1=2? No — 2>=2.
    # Actually common_prefix=2 >= 2, len_diff=0 → should accept via prefix short-circuit
    assert matches("abcde", "abxyz") is True


if __name__ == "__main__":
    import unittest
    unittest.main()
