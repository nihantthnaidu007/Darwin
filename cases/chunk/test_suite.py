from candidate import chunk


def test_empty():
    # no items: the range loop never runs and the accumulator stays empty.
    assert chunk([], 2) == []


def test_exact_multiple():
    # length is a clean multiple of size: every chunk is full, no remainder.
    assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_partial_last_chunk():
    # length is NOT a multiple of size: the final slice is short, not padded.
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_size_one():
    # size 1 yields one singleton chunk per element.
    assert chunk([1, 2, 3], 1) == [[1], [2], [3]]


def test_size_exceeds_length():
    # size larger than the input: a single chunk holding everything.
    assert chunk([1, 2, 3], 5) == [[1, 2, 3]]


def test_six_in_threes():
    assert chunk([1, 2, 3, 4, 5, 6], 3) == [[1, 2, 3], [4, 5, 6]]


def test_preserves_element_type():
    # chunking slices the sequence; element values pass through untouched.
    assert chunk(["a", "b", "c"], 2) == [["a", "b"], ["c"]]
