import pytest

from candidate import roman_from_int


def test_one():
    assert roman_from_int(1) == "I"


def test_subtraction_four():
    # 4 is IV, not IIII; the (4, "IV") entry must fire before (1, "I").
    assert roman_from_int(4) == "IV"


def test_subtraction_nine():
    assert roman_from_int(9) == "IX"


def test_additive_three():
    assert roman_from_int(3) == "III"


def test_landmark_1994():
    # M + CM + XC + IV; the canonical subtractive-heavy landmark.
    assert roman_from_int(1994) == "MCMXCIV"


def test_maximum_3999():
    # the largest representable value; MMM + CM + XC + IX.
    assert roman_from_int(3999) == "MMMCMXCIX"


def test_2024():
    assert roman_from_int(2024) == "MMXXIV"


def test_fifty_eight():
    assert roman_from_int(58) == "LVIII"


def test_forty_uses_subtractive_xl():
    # 40 is XL, not XXXX; pins the (40, "XL") entry.
    assert roman_from_int(40) == "XL"


def test_four_hundred_uses_subtractive_cd():
    assert roman_from_int(400) == "CD"


def test_2026():
    assert roman_from_int(2026) == "MMXXVI"


def test_longest_form_3888():
    # 3888 produces the maximal symbol run (MMM DCCC LXXX VIII).
    assert roman_from_int(3888) == "MMMDCCCLXXXVIII"


def test_round_trip_against_known_pairs():
    # an additive-only impl (ignoring the subtractive pairs) would return "IIII"
    # for 4 and "VIIII" for 9; pin that it does not.
    assert roman_from_int(4) != "IIII"
    assert roman_from_int(9) != "VIIII"


def test_below_range_one_raises():
    # 0 is below the valid range of 1 to 3999.
    with pytest.raises(ValueError):
        roman_from_int(0)


def test_above_range_raises():
    # 4000 is one past the ceiling of 3999.
    with pytest.raises(ValueError):
        roman_from_int(4000)


def test_negative_raises():
    with pytest.raises(ValueError):
        roman_from_int(-5)
