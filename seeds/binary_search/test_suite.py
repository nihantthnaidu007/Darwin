from candidate import binary_search


def test_present_first():
    assert binary_search([1, 3, 5, 7, 9], 1) == 0


def test_present_middle():
    assert binary_search([1, 3, 5, 7, 9], 5) == 2


def test_present_last():
    assert binary_search([1, 3, 5, 7, 9], 9) == 4


def test_absent_below_range():
    # target smaller than every element: the window collapses on the low side.
    assert binary_search([1, 3, 5, 7, 9], 0) == -1


def test_absent_between_elements():
    # target falls in a gap (4 sits between 3 and 5): not found, returns -1.
    assert binary_search([1, 3, 5, 7, 9], 4) == -1


def test_absent_above_range():
    assert binary_search([1, 3, 5, 7, 9], 10) == -1


def test_empty_returns_minus_one():
    # high = -1 < low = 0, so the loop never runs.
    assert binary_search([], 5) == -1


def test_single_element_present():
    assert binary_search([42], 42) == 0


def test_single_element_absent():
    assert binary_search([42], 7) == -1
