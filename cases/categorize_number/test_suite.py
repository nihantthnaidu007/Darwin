from candidate import categorize_number


def test_negative_short_circuits_before_anything_else():
    # negative is decided first; size/parity are never consulted.
    assert categorize_number(-1) == "negative"
    assert categorize_number(-4) == "negative"
    assert categorize_number(-1000) == "negative"


def test_zero_is_its_own_bucket():
    # zero is decided before the size/parity split; it is neither "small even" nor "large".
    assert categorize_number(0) == "zero"


def test_small_even_and_small_odd():
    assert categorize_number(2) == "small even"
    assert categorize_number(4) == "small even"
    assert categorize_number(1) == "small odd"
    assert categorize_number(99) == "small odd"


def test_small_large_boundary_at_100():
    # n <= 100 is small; 100 is the last small value and it is even.
    assert categorize_number(100) == "small even"
    # 101 is the first large value and it is odd.
    assert categorize_number(101) == "large odd"
    assert categorize_number(102) == "large even"


def test_large_even_and_large_odd():
    assert categorize_number(1000) == "large even"
    assert categorize_number(1001) == "large odd"


def test_parity_is_not_swallowed_by_size():
    # a wrong implementation that returned only size (or only parity) would fail here:
    # both halves of the label must be present and correct.
    assert categorize_number(50) == "small even"
    assert categorize_number(51) == "small odd"
    assert categorize_number(200) == "large even"
    assert categorize_number(201) == "large odd"
