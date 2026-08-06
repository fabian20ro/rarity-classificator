from __future__ import annotations


def repair(raw: str) -> str:
    """
    Perform basic repairs on raw JSON-like strings to make them parseable by standard JSON decoders.
    Removes line comments, fixes trailing decimals (e.g., '1.' -> '1.0'), 
    closes unclosed structures ('{' or '['), and removes trailing commas in objects/arrays.
    """
    s1 = _remove_line_comments(raw)
    s2 = _fix_trailing_decimal_points(s1)
    s3 = _close_unclosed_structures(s2)
    return _remove_trailing_commas(s3)


def _track_string(in_string: bool, escaped: bool, ch: str) -> tuple[bool, bool]:
    """Update string/escape state for a single character. Returns (in_string, escaped)."""
    if in_string:
        if escaped:
            return True, False
        if ch == "\\":
            return True, True
        if ch == '"':
            return False, False
        return True, False

    if ch == '"':
        return True, False

    return in_string, escaped


def _remove_line_comments(input_text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0
    while i < len(input_text):
        ch = input_text[i]
        if not in_string and ch == "/" and i + 1 < len(input_text) and input_text[i + 1] == "/":
            while out and out[-1] == " ":
                out.pop()
            j = input_text.find("\n", i)
            if j == -1:
                break
            i = j
        else:
            in_string, escaped = _track_string(in_string, escaped, ch)
            out.append(ch)
        i += 1

    return "".join(out)


def _fix_trailing_decimal_points(input_text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    for i, ch in enumerate(input_text):
        if in_string or ch != ".":
            in_string, escaped = _track_string(in_string, escaped, ch)
            out.append(ch)
            continue

        if i > 0 and input_text[i - 1].isdigit():
            nxt = input_text[i + 1] if i + 1 < len(input_text) else None
            if nxt is None or not nxt.isdigit():
                in_string, escaped = _track_string(in_string, escaped, ch)
                out.append(".0")
                continue

        in_string, escaped = _track_string(in_string, escaped, ch)
        out.append(ch)

    return "".join(out)


def _close_unclosed_structures(input_text: str) -> str:
    stack: list[str] = []
    in_string = False
    escaped = False
    for ch in input_text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                if stack and stack[-1] == '"':
                    stack.pop()
                in_string = False
            continue

        if ch == '"':
            in_string = True
            stack.append('"')
        elif ch == "{":
            stack.append("{")
        elif ch == "[":
            stack.append("[")
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()

    closers = {"{": "}", "[": "]", '"': '"'}
    suffix = "".join(closers[s] for s in reversed(stack))
    return input_text + suffix


def _remove_trailing_commas(input_text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    pending_comma = False

    for ch in input_text:
        if not in_string and ch == '"':
            if pending_comma:
                out.append(",")
                pending_comma = False
            in_string, escaped = _track_string(in_string, escaped, ch)
            out.append(ch)
        elif ch == ",":
            pending_comma = True
        elif ch in "]}":
            pending_comma = False
            in_string, escaped = _track_string(in_string, escaped, ch)
            out.append(ch)
        else:
            if pending_comma and ch.isspace():
                pass
            elif pending_comma:
                out.append(",")
                pending_comma = False

            in_string, escaped = _track_string(in_string, escaped, ch)
            out.append(ch)

    return "".join(out)
