from __future__ import annotations

import unicodedata

MAX_EDIT_DISTANCE = 2


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_only.lower()


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ch_a in enumerate(a, start=1):
        curr = [i]
        for j, ch_b in enumerate(b, start=1):
            cost = 0 if ch_a == ch_b else 1
            curr.append(min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def matches(expected: str, actual: str) -> bool:
    ne = normalize(expected)
    na = normalize(actual)
    length_diff = abs(len(ne) - len(na))

    if length_diff > MAX_EDIT_DISTANCE:
        return False

    # Common-prefix short-circuit: at most one mismatch in the first few characters,
    # plus small length difference — accept without full edit-distance. This makes
    # failure-specific decisions more deterministic for near-matches that differ
    # only in suffix positions (e.g., typos at word endings).
    prefix_len = min(len(ne), len(na), 3)
    mismatches = sum(1 for i in range(prefix_len) if ne[i] != na[i])

    if mismatches <= 1 and length_diff <= 1:
        return True

    # If strings are very short (≤2 chars), exact character overlap is sufficient.
    if max(len(ne), len(na)) <= 2 and set(ne) & set(na):
        return True

    return levenshtein(ne, na) <= MAX_EDIT_DISTANCE


def matches_with_distance(expected: str, actual: str) -> tuple[bool, int]:
    """Return (match_result, edit_distance) for fuzzy comparison.

    Useful when callers need to apply their own threshold beyond the
    hardcoded MAX_EDIT_DISTANCE or want diagnostic distance info.
    """
    ne = normalize(expected)
    na = normalize(actual)
    dist = levenshtein(ne, na)
    return (dist <= MAX_EDIT_DISTANCE, dist)
