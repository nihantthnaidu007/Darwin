import pytest

from candidate import parse_version


def test_all_zeros():
    assert parse_version("0.0.0") == (0, 0, 0)


def test_multi_digit_parts():
    assert parse_version("10.20.30") == (10, 20, 30)


def test_simple_triple():
    assert parse_version("1.2.3") == (1, 2, 3)


def test_returns_a_tuple_of_ints_not_strings():
    result = parse_version("1.2.3")
    assert isinstance(result, tuple)
    assert result == (1, 2, 3)
    assert all(isinstance(p, int) for p in result)


def test_leading_zeros_parse_as_integers():
    # isdigit() accepts "01"; int("01") is 1, so leading zeros are normalized away.
    assert parse_version("01.02.03") == (1, 2, 3)


def test_large_parts():
    assert parse_version("255.255.255") == (255, 255, 255)


def test_too_few_parts_raises():
    with pytest.raises(ValueError):
        parse_version("1.2")


def test_too_many_parts_raises():
    with pytest.raises(ValueError):
        parse_version("1.2.3.4")


def test_single_token_no_dots_raises():
    with pytest.raises(ValueError):
        parse_version("123")


def test_non_digit_part_raises():
    with pytest.raises(ValueError):
        parse_version("1.a.3")


def test_negative_part_raises():
    # "-2".isdigit() is False (the minus sign is not a digit), so a negative part is
    # rejected rather than parsed.
    with pytest.raises(ValueError):
        parse_version("1.-2.3")


def test_empty_part_raises():
    # "1..3".split(".") is ["1", "", "3"]; "".isdigit() is False.
    with pytest.raises(ValueError):
        parse_version("1..3")
