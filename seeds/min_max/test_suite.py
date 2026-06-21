import pytest

from candidate import min_max


def test_multi_element():
    assert min_max([3, 1, 2]) == (1, 3)


def test_single_element():
    # one value is both the min and the max.
    assert min_max([5]) == (5, 5)


def test_negatives():
    assert min_max([-2, -5, -1]) == (-5, -1)


def test_all_equal():
    assert min_max([4, 4, 4]) == (4, 4)


def test_sorted_ascending():
    assert min_max([1, 2, 3, 4, 5]) == (1, 5)


def test_empty_raises():
    with pytest.raises(ValueError):
        min_max([])
