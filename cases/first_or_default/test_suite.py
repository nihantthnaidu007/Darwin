from candidate import first_or_default


def test_nonempty_returns_first():
    assert first_or_default([1, 2, 3], 0) == 1
    assert first_or_default([5, 6], -1) == 5


def test_empty_returns_default():
    assert first_or_default([], 99) == 99
    assert first_or_default([], "z") == "z"


def test_string_elements():
    assert first_or_default(["a"], "z") == "a"
