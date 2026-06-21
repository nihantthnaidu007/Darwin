import pytest

from candidate import celsius_to_fahrenheit


def test_freezing_point():
    assert celsius_to_fahrenheit(0) == 32.0


def test_boiling_point():
    assert celsius_to_fahrenheit(100) == 212.0


def test_fixed_point_minus_forty():
    # -40 is the single temperature where the two scales coincide.
    assert celsius_to_fahrenheit(-40) == -40.0


def test_body_temperature():
    assert celsius_to_fahrenheit(37) == pytest.approx(98.6)


def test_absolute_zero():
    assert celsius_to_fahrenheit(-273.15) == pytest.approx(-459.67)
