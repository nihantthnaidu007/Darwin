from candidate import average


def test_empty_guard():
    assert average([]) == 0.0


def test_single():
    assert average([5]) == 5.0


def test_basic():
    assert average([2, 4]) == 3.0
    assert average([1, 2, 3, 4]) == 2.5


def test_negatives():
    assert average([-2, 2]) == 0.0


def test_floats():
    assert average([1.5, 2.5]) == 2.0
