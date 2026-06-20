import pytest

from candidate import apply_discount


def test_quarter_off():
    assert apply_discount(100, 25) == 75.0


def test_zero_percent_is_full_price():
    assert apply_discount(50, 0) == 50.0


def test_full_discount_boundary():
    # percent 100 is valid (the upper boundary): price drops to zero.
    assert apply_discount(100, 100) == 0.0


def test_zero_price_is_valid():
    # price 0 is not negative: no error, result is zero.
    assert apply_discount(0, 50) == 0.0


def test_rounded_to_two_places():
    # 19.99 * 0.9 = 17.991; round(.., 2) pins it to 17.99.
    assert apply_discount(19.99, 10) == 17.99


def test_negative_price_raises():
    with pytest.raises(ValueError):
        apply_discount(-1, 10)


def test_negative_percent_raises():
    with pytest.raises(ValueError):
        apply_discount(100, -5)


def test_percent_over_hundred_raises():
    with pytest.raises(ValueError):
        apply_discount(100, 101)
