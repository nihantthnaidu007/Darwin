import pytest

from candidate import parse_time


def test_all_zeros_is_zero():
    assert parse_time("00:00:00") == 0


def test_upper_boundary_max_time():
    # 23:59:59 is the largest valid time; 23*3600 + 59*60 + 59 = 86399.
    # This pins the upper edge so the range gate (>23, >59, >59) has teeth:
    # an impl that rejected 59 or 23 would fail here.
    assert parse_time("23:59:59") == 86399


def test_mid_afternoon():
    # 14*3600 + 30*60 + 45 = 52245.
    assert parse_time("14:30:45") == 52245


def test_single_field_contributions():
    # one unit in each field, in isolation, pins the 3600 / 60 / 1 weights.
    assert parse_time("01:00:00") == 3600
    assert parse_time("00:01:00") == 60
    assert parse_time("00:00:01") == 1


def test_noon():
    assert parse_time("12:00:00") == 43200


def test_leading_zeros_normalize_per_field():
    # isdigit() accepts "09"; int("09") is 9, so leading zeros parse as the integer.
    # 9*3600 + 8*60 + 7 = 32887.
    assert parse_time("09:08:07") == 32887


def test_returns_an_int_not_a_string():
    result = parse_time("01:00:00")
    assert isinstance(result, int)
    assert result == 3600


def test_too_few_parts_raises():
    with pytest.raises(ValueError):
        parse_time("14:30")


def test_too_many_parts_raises():
    with pytest.raises(ValueError):
        parse_time("14:30:45:00")


def test_hours_out_of_range_raises():
    # 24 is one past the valid hour ceiling of 23.
    with pytest.raises(ValueError):
        parse_time("24:00:00")


def test_minutes_out_of_range_raises():
    # 60 is one past the valid minute ceiling of 59.
    with pytest.raises(ValueError):
        parse_time("14:60:00")


def test_seconds_out_of_range_raises():
    # 60 is one past the valid second ceiling of 59. This is the field-order trap:
    # an impl that range-checked only hours and minutes would wrongly accept it.
    with pytest.raises(ValueError):
        parse_time("23:59:60")


def test_non_digit_field_raises():
    # "6a".isdigit() is False, so a trailing non-digit is rejected before int().
    with pytest.raises(ValueError):
        parse_time("14:30:6a")


def test_empty_string_raises():
    # "".split(":") is [""], length 1, so it fails the three-parts gate.
    with pytest.raises(ValueError):
        parse_time("")


def test_empty_field_raises():
    # "12::30".split(":") is ["12", "", "30"]; "".isdigit() is False.
    with pytest.raises(ValueError):
        parse_time("12::30")


def test_negative_field_raises():
    # "-1".isdigit() is False (the minus sign is not a digit), so a negative
    # field is rejected rather than parsed.
    with pytest.raises(ValueError):
        parse_time("-1:00:00")
