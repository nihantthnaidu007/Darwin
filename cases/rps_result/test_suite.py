import pytest

from candidate import rps_result


def test_rock_beats_scissors():
    assert rps_result("rock", "scissors") == "win"


def test_paper_beats_rock():
    assert rps_result("paper", "rock") == "win"


def test_scissors_beats_paper():
    assert rps_result("scissors", "paper") == "win"


def test_rock_loses_to_paper():
    assert rps_result("rock", "paper") == "lose"


def test_paper_loses_to_scissors():
    assert rps_result("paper", "scissors") == "lose"


def test_scissors_loses_to_rock():
    assert rps_result("scissors", "rock") == "lose"


def test_draw_rock():
    assert rps_result("rock", "rock") == "draw"


def test_draw_paper():
    assert rps_result("paper", "paper") == "draw"


def test_draw_scissors():
    assert rps_result("scissors", "scissors") == "draw"


def test_invalid_first_move_raises():
    with pytest.raises(ValueError):
        rps_result("lizard", "rock")


def test_invalid_second_move_raises():
    with pytest.raises(ValueError):
        rps_result("rock", "spock")
