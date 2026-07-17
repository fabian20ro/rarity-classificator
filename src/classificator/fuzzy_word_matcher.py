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
    return levenshtein(ne, na) <= MAX_EDIT_DISTANCE
