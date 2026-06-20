from candidate import running_max


def test_empty_list_is_empty():
    # no elements means the loop never runs; the result stays [].
    assert running_max([]) == []


def test_single_element():
    assert running_max([5]) == [5]


def test_mixed_sequence():
    # the running maximum is non-decreasing and equals the max of every prefix.
    assert running_max([3, 1, 4, 1, 5, 9, 2]) == [3, 3, 4, 4, 5, 9, 9]


def test_strictly_descending_holds_the_first():
    # nothing ever beats the opening value, so it repeats the whole way down.
    assert running_max([9, 5, 1]) == [9, 9, 9]


def test_all_negative_proves_none_sentinel():
    # the first element is -3. If the running max were seeded with 0 (or any
    # non-negative seed) instead of the None sentinel, the first output would be
    # 0, not -3. The None-first guard is what makes the opening element be taken
    # verbatim regardless of sign.
    assert running_max([-3, -5, -1]) == [-3, -3, -1]


def test_single_negative_also_proves_sentinel():
    assert running_max([-10]) == [-10]


def test_strictly_ascending_tracks_each_new_max():
    assert running_max([1, 2, 3, 4]) == [1, 2, 3, 4]


def test_equal_values_use_non_strict_carry():
    # n > current is strict, so a tie does not replace current; the value is the
    # same anyway, so equal inputs reproduce themselves.
    assert running_max([4, 4, 4]) == [4, 4, 4]


def test_crossing_zero():
    assert running_max([0, -1, 5, -2]) == [0, 0, 5, 5]


def test_length_is_preserved():
    # one output per input, in order.
    src = [3, 1, 4, 1, 5, 9, 2]
    result = running_max(src)
    assert len(result) == len(src)


def test_result_is_non_decreasing():
    # the defining property of a running maximum.
    result = running_max([5, 2, 8, 8, 1, 10, 3])
    assert all(result[i] <= result[i + 1] for i in range(len(result) - 1))
