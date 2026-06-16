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
