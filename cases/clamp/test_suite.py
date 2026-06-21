from candidate import clamp


def test_in_range_unchanged():
    assert clamp(5, 0, 10) == 5


def test_below_low_returns_low():
    assert clamp(-3, 0, 10) == 0


def test_above_high_returns_high():
    assert clamp(15, 0, 10) == 10


def test_at_low_boundary_returns_value():
    # value == low is NOT below low, so the original value is returned.
    assert clamp(0, 0, 10) == 0


def test_at_high_boundary_returns_value():
    # value == high is NOT above high, so the original value is returned.
    assert clamp(10, 0, 10) == 10


def test_degenerate_range():
    # low == high: any value collapses to that single point.
    assert clamp(7, 7, 7) == 7
