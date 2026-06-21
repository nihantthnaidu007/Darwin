from candidate import group_by_key


def test_empty():
    assert group_by_key([]) == {}


def test_single_pair():
    assert group_by_key([("x", 10)]) == {"x": [10]}


def test_single_key_repeated_keeps_order():
    # one key seen twice: both values land in one list, in arrival order.
    assert group_by_key([("a", 1), ("a", 2)]) == {"a": [1, 2]}


def test_multiple_keys_interleaved():
    # keys interleave; each key's value list preserves arrival order across the gap.
    assert group_by_key([("a", 1), ("b", 2), ("a", 3)]) == {"a": [1, 3], "b": [2]}


def test_three_keys():
    pairs = [("r", 1), ("g", 2), ("b", 3), ("g", 4), ("r", 5)]
    assert group_by_key(pairs) == {"r": [1, 5], "g": [2, 4], "b": [3]}


def test_value_list_is_a_list():
    # setdefault seeds a real list per key; the grouped values are appended to it.
    result = group_by_key([("k", 1), ("k", 2), ("k", 3)])
    assert result == {"k": [1, 2, 3]}
    assert isinstance(result["k"], list)
