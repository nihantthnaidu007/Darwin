from candidate import merge_inventory


def test_shared_key_sums():
    assert merge_inventory({"apple": 3}, {"apple": 2}) == {"apple": 5}


def test_key_in_only_one_input_carries_over():
    # apple is only in a, banana only in b; both are positive and both survive.
    assert merge_inventory({"apple": 3}, {"banana": 5}) == {"apple": 3, "banana": 5}


def test_positive_and_negative_cancel_to_zero_is_dropped():
    # 2 + (-2) = 0, and 0 is not strictly greater than 0, so the key is dropped.
    assert merge_inventory({"x": 2}, {"x": -2}) == {}


def test_negative_in_only_one_input_is_dropped_by_the_sum_rule():
    # x appears only in a with -3: the SUM is -3 (not >0) so x is dropped; y sums to
    # 1 and survives. This pins that >0 is tested on the merged total, not per input.
    assert merge_inventory({"x": -3}, {"y": 1}) == {"y": 1}


def test_two_empty_inventories_yield_empty():
    assert merge_inventory({}, {}) == {}


def test_mixed_case_exercises_sum_carryover_and_drop_together():
    # a: 5, b: 3, c: -1 ; b: 2, c: 1, d: 4
    #   a -> 5 (carry-over, kept)
    #   b -> 5 (sum, kept)
    #   c -> 0 (cancels, dropped)
    #   d -> 4 (carry-over, kept)
    assert merge_inventory(
        {"a": 5, "b": 3, "c": -1}, {"b": 2, "c": 1, "d": 4}
    ) == {"a": 5, "b": 5, "d": 4}


def test_all_negative_totals_drop_to_empty():
    # every name's total is <= 0, so nothing survives.
    assert merge_inventory({"x": -1, "y": -2}, {}) == {}
    assert merge_inventory({"x": -1}, {"x": -1}) == {}
