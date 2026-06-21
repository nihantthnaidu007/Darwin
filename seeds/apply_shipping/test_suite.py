from candidate import apply_shipping


def test_express_multiplier_applies_before_the_minimum_floor():
    # base = 1*0.5 + 1*0.1 = 0.6 ; express *1.5 = 0.9 ; 0.9 < 5.0 so the minimum
    # floors it to 5.0. This pins the ORDER: multiply first, then floor. A version
    # that floored first (0.6 -> 5.0) and then multiplied would return 7.5, not 5.0.
    assert apply_shipping(1, 1, True) == 5.0


def test_natural_cost_above_floor_without_and_with_express():
    # base = 6*0.5 + 28*0.1 = 5.8 (above the 5.0 floor, returned unchanged).
    assert apply_shipping(6, 28, False) == 5.8
    # the same base with express multiplies by 1.5: 5.8 * 1.5 = 8.7.
    assert apply_shipping(6, 28, True) == 8.7


def test_round_to_two_decimals_is_load_bearing():
    # both bases evaluate to a float just past the clean value
    # (5.800000000000001 and 8.700000000000001); the trailing round collapses them
    # to 5.8 and 8.7. An implementation that strips the round returns the noisy
    # float, which is NOT equal to the clean two-decimal value asserted here.
    assert apply_shipping(6, 28, False) == 5.8
    assert apply_shipping(6, 28, True) == 8.7
    # equality (not approx) is deliberate: approx would mask a dropped round.
    assert apply_shipping(6, 28, False) != 5.800000000000001


def test_zero_weight_and_distance_floors_to_the_minimum():
    # base 0.0 is below 5.0 and floors up, whether or not express is set
    # (0.0 * 1.5 is still 0.0).
    assert apply_shipping(0, 0, False) == 5.0
    assert apply_shipping(0, 0, True) == 5.0


def test_minimum_floor_uses_strict_less_than():
    # 9*0.5 = 4.5 is below 5.0 and floors up to 5.0.
    assert apply_shipping(9, 0, False) == 5.0
    # 10*0.5 = 5.0 is NOT below 5.0 (strict <), so it is left at 5.0, not re-floored.
    assert apply_shipping(10, 0, False) == 5.0
    # 10*0.5 + 1*0.1 = 5.1 is above the floor and returned unchanged.
    assert apply_shipping(10, 1, False) == 5.1


def test_larger_express_order():
    # base = 20*0.5 + 30*0.1 = 13.0 ; express *1.5 = 19.5.
    assert apply_shipping(20, 30, True) == 19.5
    # the same order without express returns the un-multiplied base.
    assert apply_shipping(20, 30, False) == 13.0
