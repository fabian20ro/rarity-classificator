from classificator.json_repair import repair


def test_removes_trailing_comma_in_array():
    assert repair("[1, 2, ]") in {"[1, 2]", "[1,2]"}


def test_preserves_comma_before_non_space_character():
    assert repair("[1, 2,a]") in {"[1, 2,a]", "[1,2,a]"}


def test_closes_unclosed_object_and_array():
    assert repair('[{"id": 1') == '[{"id": 1}]'

def test_fix_trailing_decimal_point():
    assert repair('{"val": 1.}') == '{"val": 1.0}'
