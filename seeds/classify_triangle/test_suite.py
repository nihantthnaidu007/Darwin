import pytest

from candidate import classify_triangle


def test_equilateral():
    assert classify_triangle(3, 3, 3) == "equilateral"


def test_isosceles_sorted_equal_pair():
    # two equal sides given in non-descending order.
    assert classify_triangle(5, 5, 8) == "isosceles"


def test_scalene():
    assert classify_triangle(4, 5, 6) == "scalene"


def test_isosceles_unsorted_b_equals_c():
    # the equal pair is b and c with the odd side first. The classification checks
    # all three pairs (a==b or b==c or a==c), so order does not matter; an impl
    # that only compared sorted-adjacent sides would misread this.
    assert classify_triangle(8, 5, 5) == "isosceles"


def test_isosceles_unsorted_a_equals_c():
    # the equal pair is a and c, straddling the odd side. Exercises the a==c branch.
    assert classify_triangle(5, 8, 5) == "isosceles"


def test_scalene_right_triangle():
    # a 6-8-10 right triangle is still scalene; the classifier ignores angles.
    assert classify_triangle(6, 8, 10) == "scalene"


def test_equilateral_large():
    assert classify_triangle(10, 10, 10) == "equilateral"


def test_isosceles_small():
    assert classify_triangle(2, 2, 3) == "isosceles"


def test_degenerate_one_one_five_raises():
    # 1 + 1 = 2 <= 5, so the two short sides cannot reach across; not a triangle.
    with pytest.raises(ValueError):
        classify_triangle(1, 1, 5)


def test_exact_degenerate_raises():
    # 1 + 2 == 3 exactly: a straight line, not a triangle. The gate is <=, not <,
    # so the equality case is rejected.
    with pytest.raises(ValueError):
        classify_triangle(1, 2, 3)


def test_degenerate_unsorted_raises():
    # same degenerate triple as (1, 1, 5) but with the long side first; the sort
    # inside the function normalizes order before the inequality check.
    with pytest.raises(ValueError):
        classify_triangle(5, 1, 1)


def test_zero_side_raises():
    with pytest.raises(ValueError):
        classify_triangle(0, 4, 5)


def test_zero_side_in_last_position_raises():
    # the positivity guard checks every side, not just the first.
    with pytest.raises(ValueError):
        classify_triangle(4, 5, 0)


def test_negative_side_raises():
    with pytest.raises(ValueError):
        classify_triangle(-3, 4, 5)
