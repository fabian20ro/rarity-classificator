from classificator.json_repair import repair


def test_removes_trailing_comma_in_array():
    assert repair("[1, 2, ]") in {"[1, 2]", "[1,2]"}


def test_preserves_comma_before_non_space_character():
    assert repair("[1, 2,a]") in {"[1, 2,a]", "[1,2,a]"}


def test_closes_unclosed_object_and_array():
    assert repair('[{"id": 1') == '[{"id": 1}]'


def test_fix_trailing_decimal_point():
    assert repair('{"val": 1.}') == '{"val": 1.0}'


def test_handles_comment_in_string():
    assert repair('{"url": "http://example.com/api/v1/data//"}') == '{"url": "http://example.com/api/v1/data//"}'


def test_removes_line_comment():
    assert repair('{"a": 1 // comment\n}') == '{"a": 1}'


def test_removes_trailing_commas_in_object():
    assert repair('{"a": 1,}') == '{"a": 1}'


def test_line_comment_at_eof_without_newline():
    assert repair('{"a": 1 // comment') == '{"a": 1}'


def test_nested_unclosed_objects_and_arrays():
    result = repair('[{"x": [')
    assert result == '[{"x": []}]' or result == '[{"x":[]}]'


def test_multiple_trailing_commas_in_array():
    assert repair("[1, 2,,]") in {"[1, 2]", "[1,2]"}


def test_decimal_inside_string_preserved():
    assert repair('{"key": "3.14"}') == '{"key": "3.14"}'


def test_comment_does_not_consume_next_line():
    result = repair('{"a": 1 // comment\n{"b": 2}')
    assert '"b"' in result
    assert '2' in result


def test_already_valid_json_passthrough():
    import json as _json
    original = '{"x": [1, 2], "y": {"z": true}}'
    result = repair(original)
    parsed = _json.loads(result)
    assert parsed == {"x": [1, 2], "y": {"z": True}}


def test_empty_input_handled():
    result = repair("")
    assert isinstance(result, str)


def test_mixed_comment_and_unclosed_structure():
    result = repair('{"a": 1 // comment\n"b":')
    assert '"b"' in result



def test_escape_in_string_preserves_subsequent_slashes():
    # Regression: _track_string must keep in_string=True after a backslash
    # inside a JSON string; otherwise the "//" would be stripped as a comment.
    assert repair('{"url": "http://x.com/a\\n//b"}') == '{"url": "http://x.com/a\\n//b"}'


def test_block_comment_stripped_by_repair():
    # Regression: _remove_line_comments handles /* ... */ but no public-API test existed.
    import json as _json
    result = repair('{"a": 1 /* comment */\n}')
    parsed = _json.loads(result)
    assert parsed == {"a": 1}


def test_unclosed_string_gets_closing_quote():
    # Regression: _close_unclosed_structures appends a closing " for unmatched strings.
    import json as _json
    result = repair('{"key": "value')
    parsed = _json.loads(result)
    assert parsed == {"key": "value"}


def test_mixed_comment_and_unclosed_structure():
    result = repair('{"a": 1 // comment\n"b":')
    assert '"b"' in result
