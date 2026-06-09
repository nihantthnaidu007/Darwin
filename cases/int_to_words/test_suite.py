import pytest

from candidate import int_to_words


def test_zero():
    assert int_to_words(0) == "zero"


def test_single_digits():
    assert int_to_words(1) == "one"
    assert int_to_words(7) == "seven"
    assert int_to_words(9) == "nine"


def test_teens():
    assert int_to_words(10) == "ten"
    assert int_to_words(13) == "thirteen"
    assert int_to_words(19) == "nineteen"


def test_round_tens():
    assert int_to_words(20) == "twenty"
    assert int_to_words(70) == "seventy"
    assert int_to_words(90) == "ninety"


def test_compound_tens_are_hyphenated():
    assert int_to_words(21) == "twenty-one"
    assert int_to_words(42) == "forty-two"
    assert int_to_words(99) == "ninety-nine"


def test_round_hundred():
    assert int_to_words(100) == "one hundred"
    assert int_to_words(800) == "eight hundred"


def test_hundreds_with_remainder_no_and():
    assert int_to_words(142) == "one hundred forty-two"
    assert int_to_words(305) == "three hundred five"
    assert int_to_words(999) == "nine hundred ninety-nine"


def test_round_thousand():
    assert int_to_words(1000) == "one thousand"


def test_thousands():
    assert int_to_words(1234) == "one thousand two hundred thirty-four"
    assert int_to_words(10000) == "ten thousand"
    assert int_to_words(100000) == "one hundred thousand"


def test_millions():
    assert int_to_words(1000000) == "one million"
    assert (int_to_words(1234567)
            == "one million two hundred thirty-four thousand "
               "five hundred sixty-seven")


def test_billions():
    assert int_to_words(1000000000) == "one billion"


def test_skips_empty_groups():
    assert int_to_words(1000001) == "one million one"
    assert int_to_words(2000000) == "two million"


def test_max_boundary():
    assert (int_to_words(999_999_999_999)
            == "nine hundred ninety-nine billion "
               "nine hundred ninety-nine million "
               "nine hundred ninety-nine thousand "
               "nine hundred ninety-nine")


def test_negative():
    assert int_to_words(-42) == "negative forty-two"
    assert int_to_words(-1000001) == "negative one million one"


def test_out_of_range_raises_value_error():
    with pytest.raises(ValueError):
        int_to_words(1_000_000_000_000)
    with pytest.raises(ValueError):
        int_to_words(-1_000_000_000_000)


def test_non_int_raises_type_error():
    with pytest.raises(TypeError):
        int_to_words(3.0)
    with pytest.raises(TypeError):
        int_to_words("5")


def test_bool_rejected_as_non_int():
    with pytest.raises(TypeError):
        int_to_words(True)
