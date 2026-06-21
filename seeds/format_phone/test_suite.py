import pytest

from candidate import format_phone


def test_formats_ten_digits_into_grouped_string():
    assert format_phone("5551234567") == "(555) 123-4567"
    assert format_phone("1234567890") == "(123) 456-7890"


def test_all_zero_digits_format_verbatim():
    # zeros are digits; nothing is stripped or collapsed.
    assert format_phone("0000000000") == "(000) 000-0000"
    assert format_phone("9999999999") == "(999) 999-9999"


def test_group_boundaries_are_3_3_4():
    # the slices are [0:3], [3:6], [6:10]; a distinct digit per position proves no
    # off-by-one in the grouping.
    assert format_phone("0123456789") == "(012) 345-6789"


def test_too_few_digits_raise():
    with pytest.raises(ValueError):
        format_phone("123")
    with pytest.raises(ValueError):
        format_phone("")


def test_too_many_digits_raise():
    with pytest.raises(ValueError):
        format_phone("55512345678")


def test_non_digit_in_ten_chars_raises():
    # length is exactly 10 but the trailing character is not a digit, so isdigit()
    # is False and the guard rejects it.
    with pytest.raises(ValueError):
        format_phone("555123456a")


def test_error_message_echoes_the_offending_input():
    with pytest.raises(ValueError) as exc:
        format_phone("123")
    assert "123" in str(exc.value)
