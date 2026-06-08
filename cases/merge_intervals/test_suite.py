from candidate import merge_intervals


def test_empty():
    assert merge_intervals([]) == []


def test_single():
    assert merge_intervals([[1, 3]]) == [[1, 3]]


def test_non_overlapping_sorted():
    assert merge_intervals([[1, 2], [3, 4]]) == [[1, 2], [3, 4]]


def test_overlapping():
    assert merge_intervals([[1, 3], [2, 6]]) == [[1, 6]]


def test_nested():
    assert merge_intervals([[1, 10], [2, 3]]) == [[1, 10]]


def test_unsorted_input():
    assert merge_intervals([[3, 4], [1, 2]]) == [[1, 2], [3, 4]]


def test_touching_merges():
    # end == next start -> merge
    assert merge_intervals([[1, 2], [2, 3]]) == [[1, 3]]


def test_duplicates():
    assert merge_intervals([[1, 3], [1, 3]]) == [[1, 3]]


def test_multiple_groups():
    assert merge_intervals([[1, 4], [2, 5], [7, 9], [8, 10]]) == [[1, 5], [7, 10]]


def test_negative_coordinates():
    assert merge_intervals([[-5, -1], [-3, 0]]) == [[-5, 0]]


def test_chain_all_merge():
    assert merge_intervals([[1, 2], [2, 3], [3, 4], [4, 5]]) == [[1, 5]]


def test_same_start_different_end():
    assert merge_intervals([[1, 4], [1, 2]]) == [[1, 4]]


def test_inner_interval_fully_swallowed_midway():
    assert merge_intervals([[1, 5], [2, 3], [4, 8]]) == [[1, 8]]


def test_does_not_mutate_input():
    data = [[1, 3], [2, 4]]
    snapshot = [list(iv) for iv in data]
    merge_intervals(data)
    assert data == snapshot


def test_tuple_intervals():
    assert merge_intervals([(1, 3), (2, 6)]) == [[1, 6]]


def test_returns_lists_not_tuples():
    result = merge_intervals([(1, 2)])
    assert result == [[1, 2]]
    assert isinstance(result[0], list)
