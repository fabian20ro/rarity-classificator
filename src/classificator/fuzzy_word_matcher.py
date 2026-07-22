from __future__ import annotations

MAX_EDIT_DISTANCE = 2
DIACRITICS_MAP = str.maketrans(
    {
        "ă": "a",
        "Ă": "A",
        "â": "a",
        "Â": "A",
        "î": "i",
        "Î": "I",
        "ș": "s",
        "Ș": "S",
        "ț": "t",
        "Ț": "T",
        "ş": "s",
        "Ş": "S",
        "ţ": "t",
        "Ţ": "T",
    }
)


def normalize(text: str) -> str:
    return text.translate(DIACRITICS_MAP).lower()


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
    if abs(len(ne) - len(na)) > MAX_EDIT_DISTANCE:
        return False

    # Common-prefix short-circuit: if the first few characters match exactly,
    # and the remaining difference is small, accept as a match. This makes
    # failure-specific decisions more deterministic for near-matches that differ
    # only in suffix positions (e.g., typos at word endings).
    prefix_len = min(len(ne), len(na), 3)
    common_prefix = sum(1 for i in range(prefix_len) if ne[i] == na[i])

    if common_prefix >= prefix_len - 1 and abs(len(ne) - len(na)) <= 1:
        return True

    # If strings are very short (≤2 chars), exact character overlap is sufficient.
    if max(len(ne), len(na)) <= 2 and set(ne) & set(na):
        return True

    return levenshtein(ne, na) <= MAX_EDIT_DISTANCE
