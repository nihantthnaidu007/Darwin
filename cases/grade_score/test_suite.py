import pytest

from candidate import grade_score


def test_a_band_and_upper_extreme():
    assert grade_score(100) == "A"
    assert grade_score(95) == "A"
    assert grade_score(90) == "A"


def test_a_b_boundary_at_90_vs_89():
    # 90 is the first A; 89 is the last B. A one-off threshold would swap these.
    assert grade_score(90) == "A"
    assert grade_score(89) == "B"


def test_b_band_and_b_c_boundary_at_80_vs_79():
    assert grade_score(85) == "B"
    assert grade_score(80) == "B"
    assert grade_score(79) == "C"


def test_c_band_and_c_d_boundary_at_70_vs_69():
    assert grade_score(75) == "C"
    assert grade_score(70) == "C"
    assert grade_score(69) == "D"


def test_d_band_and_d_f_boundary_at_60_vs_59():
    assert grade_score(65) == "D"
    assert grade_score(60) == "D"
    assert grade_score(59) == "F"


def test_f_band_and_lower_extreme():
    assert grade_score(30) == "F"
    assert grade_score(0) == "F"


def test_below_range_raises():
    with pytest.raises(ValueError):
        grade_score(-1)
    with pytest.raises(ValueError):
        grade_score(-100)


def test_above_range_raises():
    with pytest.raises(ValueError):
        grade_score(101)
    with pytest.raises(ValueError):
        grade_score(200)


def test_error_message_echoes_the_score():
    with pytest.raises(ValueError) as exc:
        grade_score(150)
    assert "150" in str(exc.value)
