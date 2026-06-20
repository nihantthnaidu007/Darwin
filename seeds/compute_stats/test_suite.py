import pytest

from candidate import compute_stats


def test_multi_element():
    assert compute_stats([1, 2, 3, 4]) == {"min": 1, "max": 4, "mean": 2.5}


def test_single_element():
    # one value is its own min, max, and mean.
    assert compute_stats([5]) == {"min": 5, "max": 5, "mean": 5.0}


def test_negatives_mean_zero():
    assert compute_stats([-3, 0, 3]) == {"min": -3, "max": 3, "mean": 0.0}


def test_integer_mean():
    # 6 / 3 = 2.0; rounding leaves it unchanged.
    assert compute_stats([1, 2, 3]) == {"min": 1, "max": 3, "mean": 2.0}


def test_mean_rounded_to_four_places():
    # 5 / 3 = 1.66666...; round(.., 4) pins it to 1.6667.
    assert compute_stats([1, 2, 2]) == {"min": 1, "max": 2, "mean": 1.6667}


def test_empty_raises():
    with pytest.raises(ValueError):
        compute_stats([])
