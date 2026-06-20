from candidate import sum_evens


def test_basic_mixed():
    assert sum_evens([1, 2, 3, 4, 5, 6]) == 12


def test_empty():
    assert sum_evens([]) == 0


def test_all_odd():
    assert sum_evens([1, 3, 5, 7, 9]) == 0


def test_all_even():
    assert sum_evens([2, 4, 6, 8]) == 20


def test_negatives():
    assert sum_evens([-2, -4, -6]) == -12


def test_negative_odds_excluded():
    assert sum_evens([-1, -3, -5]) == 0


def test_mixed_signs():
    # evens are -2, 0, 4  ->  2
    assert sum_evens([-3, -2, 0, 1, 4]) == 2


def test_zero_only():
    assert sum_evens([0]) == 0


def test_single_even():
    assert sum_evens([8]) == 8


def test_single_odd():
    assert sum_evens([7]) == 0


def test_tuple_input():
    assert sum_evens((10, 15, 20, 25)) == 30


def test_large_input():
    # evens 2..1000 -> 250500
    assert sum_evens(list(range(1, 1001))) == 250500


def test_does_not_sum_everything():
    # an impl that summed ALL numbers would return 10 here, not 6
    assert sum_evens([1, 2, 3, 4]) == 6


def test_does_not_count_evens():
    # an impl that counted evens would return 2 here, not 30
    assert sum_evens([10, 20, 5]) == 30


def test_duplicate_evens_not_deduped():
    # a "sum of DISTINCT evens" bug would return 2 here, not 6
    assert sum_evens([2, 2, 2]) == 6


def test_repeated_evens_with_odds():
    # dedup bug -> 10 (4+6); correct -> 20
    assert sum_evens([4, 4, 3, 6, 6]) == 20
