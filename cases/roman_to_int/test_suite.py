import pytest

from candidate import roman_to_int


def test_single_symbols():
    assert roman_to_int("I") == 1
    assert roman_to_int("V") == 5
    assert roman_to_int("X") == 10
    assert roman_to_int("L") == 50
    assert roman_to_int("C") == 100
    assert roman_to_int("D") == 500
    assert roman_to_int("M") == 1000


def test_additive_runs():
    assert roman_to_int("III") == 3
    assert roman_to_int("VIII") == 8
    assert roman_to_int("LVIII") == 58


def test_subtraction_pairs():
    # the heart of the numeral system: a smaller symbol before a larger subtracts.
    assert roman_to_int("IV") == 4
    assert roman_to_int("IX") == 9
    assert roman_to_int("XL") == 40
    assert roman_to_int("XC") == 90
    assert roman_to_int("CD") == 400
    assert roman_to_int("CM") == 900


def test_subtraction_is_not_addition():
    # an impl that ignored ordering and summed symbols would return 6 / 11 here.
    assert roman_to_int("IV") != 6
    assert roman_to_int("IX") != 11


def test_compound_values():
    assert roman_to_int("XLII") == 42
    assert roman_to_int("DCCCXC") == 890
    assert roman_to_int("MMXXVI") == 2026
    assert roman_to_int("MMMDCCCLXXXVIII") == 3888


def test_canonical_landmarks():
    assert roman_to_int("MCMXCIV") == 1994
    assert roman_to_int("MMMCMXCIX") == 3999


def test_empty_string_is_zero():
    # the reference loops over nothing and returns the initial total.
    assert roman_to_int("") == 0


def test_invalid_letter_raises():
    with pytest.raises(ValueError):
        roman_to_int("A")


def test_invalid_letter_inside_otherwise_valid_raises():
    with pytest.raises(ValueError):
        roman_to_int("XIZ")
