import pytest

from candidate import income_tax


def test_zero_income():
    assert income_tax(0) == 0


def test_within_zero_bracket():
    assert income_tax(5_000_00) == 0


def test_at_first_threshold_still_zero():
    # Exactly $10,000: the entire amount sits in the 0% bracket.
    assert income_tax(10_000_00) == 0


def test_just_below_threshold():
    assert income_tax(9_999_99) == 0


def test_per_bracket_floor_rounding():
    # $10,000.10 -> 10 cents taxed at 10% -> 1 cent (floored).
    assert income_tax(10_000_10) == 1


def test_one_cent_in_bracket_floors_to_zero():
    assert income_tax(10_000_01) == 0


def test_into_ten_percent_bracket():
    # $20,000: $10k taxed at 10% -> $1,000.
    assert income_tax(20_000_00) == 100000


def test_at_second_threshold():
    # $40,000: $30k at 10% -> $3,000.
    assert income_tax(40_000_00) == 300000


def test_into_twenty_two_percent_bracket():
    # $50,000: $30k@10% + $10k@22% = $3,000 + $2,200 = $5,200.
    assert income_tax(50_000_00) == 520000


def test_at_third_threshold():
    # $85,000: $30k@10% + $45k@22% = $3,000 + $9,900 = $12,900.
    assert income_tax(85_000_00) == 1290000


def test_into_thirty_two_percent_bracket():
    # $100,000: 3,000 + 9,900 + $15k@32% (4,800) = $17,700.
    assert income_tax(100_000_00) == 1770000


def test_at_top_threshold():
    # $160,000: 3,000 + 9,900 + $75k@32% (24,000) = $36,900.
    assert income_tax(160_000_00) == 3690000


def test_into_top_bracket():
    # $200,000: 3,000 + 9,900 + 24,000 + $40k@37% (14,800) = $51,700.
    assert income_tax(200_000_00) == 5170000


def test_negative_raises_value_error():
    with pytest.raises(ValueError):
        income_tax(-1)


def test_non_int_raises_type_error():
    with pytest.raises(TypeError):
        income_tax(50_000.0)
    with pytest.raises(TypeError):
        income_tax("50000")


def test_bool_rejected_as_non_int():
    with pytest.raises(TypeError):
        income_tax(True)
