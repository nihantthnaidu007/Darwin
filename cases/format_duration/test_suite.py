import pytest

from candidate import format_duration


def test_zero_is_now():
    assert format_duration(0) == "now"


def test_one_second_singular():
    assert format_duration(1) == "1 second"


def test_many_seconds_plural():
    assert format_duration(59) == "59 seconds"


def test_round_minute_singular():
    assert format_duration(60) == "1 minute"


def test_minute_and_one_second():
    assert format_duration(61) == "1 minute and 1 second"


def test_minute_and_seconds():
    assert format_duration(62) == "1 minute and 2 seconds"


def test_round_minutes_plural_drops_zero_seconds():
    assert format_duration(120) == "2 minutes"


def test_round_hour():
    assert format_duration(3600) == "1 hour"


def test_hour_minute_seconds_join_grammar():
    assert format_duration(3662) == "1 hour, 1 minute and 2 seconds"


def test_round_day():
    assert format_duration(86400) == "1 day"


def test_four_components():
    assert format_duration(90061) == "1 day, 1 hour, 1 minute and 1 second"


def test_round_year_singular():
    assert format_duration(31536000) == "1 year"


def test_years_plural():
    assert format_duration(63072000) == "2 years"


def test_all_five_units():
    assert (format_duration(31627810)
            == "1 year, 1 day, 1 hour, 30 minutes and 10 seconds")


def test_negative_raises_value_error():
    with pytest.raises(ValueError):
        format_duration(-1)


def test_non_int_raises_type_error():
    with pytest.raises(TypeError):
        format_duration(60.0)
    with pytest.raises(TypeError):
        format_duration("60")


def test_bool_rejected_as_non_int():
    with pytest.raises(TypeError):
        format_duration(True)
