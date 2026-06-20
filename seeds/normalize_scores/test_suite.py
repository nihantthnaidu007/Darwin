from candidate import normalize_scores


def test_empty():
    assert normalize_scores([]) == []


def test_single_is_zero():
    assert normalize_scores([5]) == [0.0]


def test_all_equal_are_zero():
    assert normalize_scores([2, 2, 2]) == [0.0, 0.0, 0.0]


def test_min_max_scaling():
    assert normalize_scores([0, 5, 10]) == [0.0, 0.5, 1.0]
    assert normalize_scores([1, 3]) == [0.0, 1.0]


def test_negatives():
    assert normalize_scores([-2, 2]) == [0.0, 1.0]
