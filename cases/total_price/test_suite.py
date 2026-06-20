import pytest

from candidate import total_price


def test_empty_is_zero():
    # no lines, no discounts: the loop never runs and the total stays the initial 0.
    assert total_price([]) == 0


def test_single_line_no_discounts():
    assert total_price([["apple", 2.5, 4]]) == pytest.approx(10.0)


def test_multi_line_no_discounts():
    # 10*2 + 5*3 = 35, no quantity over 10, total under 1000.
    assert total_price([["a", 10, 2], ["b", 5, 3]]) == 35


def test_line_discount_boundary_at_quantity_10_vs_11():
    # quantity 10 is NOT over 10: no per-line discount. 100*10 = 1000.
    assert total_price([["a", 100, 10]]) == 1000
    # quantity 11 IS over 10: the line gets 10 percent off. 100*11*0.9 = 990.0.
    assert total_price([["a", 100, 11]]) == pytest.approx(990.0)


def test_order_discount_boundary_exactly_1000_vs_just_over():
    # total exactly 1000 is NOT over 1000: no order discount.
    assert total_price([["a", 100, 10]]) == 1000
    # one cent over the line above tips it past 1000: 1001 * 0.95 = 950.95.
    assert total_price([["a", 100, 10], ["b", 1, 1]]) == pytest.approx(950.95)


def test_both_discounts_stack():
    # line discounts apply first (per qty>10 line), then the 5 percent order discount
    # on the resulting total.
    # 500*20*0.9 = 9000.0 ; 100*11*0.9 = 990.0 ; total 9990.0 ; *0.95 = 9490.5.
    assert total_price([["a", 500, 20], ["b", 100, 11]]) == pytest.approx(9490.5)


def test_result_is_rounded_to_two_decimals():
    # 3 * 0.1 = 0.30000000000000004 before rounding; the reference rounds to 2 places.
    assert total_price([["a", 0.1, 3]]) == pytest.approx(0.3)
