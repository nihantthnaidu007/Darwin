"""Strict test suite for the rate_limiter unit (MCASE_UNIT selects the unit)."""
import os
from pathlib import Path

import pytest
from mdiffer import load_unit

UNIT_DIR = Path(__file__).parent / os.environ.get("MCASE_UNIT", "original")
Limiter = load_unit(UNIT_DIR).Limiter

RATE_MSG = "rate must be an integer between 1 and 100"
BURST_MSG = "burst must be an integer between 1 and 100"
CLIENT_MSG = "client must be a non-empty string of at most 64 characters"
TICK_MSG = "n must be a positive integer"


# ---------------------------------------------------------------- normal

def test_first_touch_bucket_is_full():
    lim = Limiter(1, 3)
    assert [lim.allow("c") for _ in range(3)] == [True, True, True]
    assert lim.allow("c") is False


def test_refill_after_ticks():
    lim = Limiter(2, 3)
    for _ in range(3):
        lim.allow("c")
    assert lim.allow("c") is False
    lim.tick(1)                          # +2 tokens
    assert lim.remaining("c") == 2
    assert lim.allow("c") is True
    assert lim.allow("c") is True
    assert lim.allow("c") is False


def test_refill_clamps_at_burst():
    lim = Limiter(10, 4)
    lim.allow("c")
    lim.tick(50)
    assert lim.remaining("c") == 4


def test_clients_are_independent():
    lim = Limiter(1, 1)
    assert lim.allow("a") is True
    assert lim.allow("a") is False
    assert lim.allow("b") is True


def test_remaining_does_not_consume():
    lim = Limiter(1, 2)
    lim.allow("c")
    assert lim.remaining("c") == 1
    assert lim.remaining("c") == 1


def test_tick_returns_new_time():
    lim = Limiter(1, 1)
    assert lim.tick() == 1
    assert lim.tick(4) == 5


def test_reset_refills_bucket():
    lim = Limiter(1, 2)
    lim.allow("c"); lim.allow("c")
    assert lim.allow("c") is False
    assert lim.reset("c") is True
    assert lim.remaining("c") == 2


def test_reset_unknown_returns_false():
    assert Limiter(1, 1).reset("ghost") is False


def test_active_clients_first_touch_order():
    lim = Limiter(1, 5)
    lim.allow("zeta"); lim.allow("alpha"); lim.allow("zeta"); lim.allow("mid")
    assert lim.active_clients() == ["zeta", "alpha", "mid"]


def test_stats():
    lim = Limiter(1, 1)
    lim.allow("a")            # allowed
    lim.allow("a")            # denied
    lim.reset("a")
    lim.tick(2)
    assert lim.stats() == {"time": 2, "clients": 1, "allowed": 1,
                           "denied": 1, "resets": 1}


# ------------------------------------------------------------ edge cases

def test_remaining_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        Limiter(1, 1).remaining("ghost")


def test_denied_at_exact_zero_then_refill_boundary():
    lim = Limiter(1, 1)
    assert lim.allow("c") is True
    assert lim.allow("c") is False     # exactly zero tokens
    lim.tick(1)
    assert lim.allow("c") is True      # exactly one token refilled


def test_late_first_touch_still_full():
    lim = Limiter(1, 3)
    lim.tick(10)
    assert [lim.allow("c") for _ in range(4)] == [True, True, True, False]


# ------------------------------------------------- boundary / validation

def test_constructor_boundaries():
    Limiter(1, 1)
    Limiter(100, 100)
    for bad in (0, 101, True, False, "5", 1.5, None):
        with pytest.raises(ValueError, match=f"^{RATE_MSG}$"):
            Limiter(bad, 5)
        with pytest.raises(ValueError, match=f"^{BURST_MSG}$"):
            Limiter(5, bad)


def test_rate_validated_before_burst():
    with pytest.raises(ValueError, match=f"^{RATE_MSG}$"):
        Limiter(0, 0)


def test_client_validation_on_every_client_method():
    lim = Limiter(1, 1)
    for method in (lim.allow, lim.remaining, lim.reset):
        for bad in ("", "x" * 65, 7, None, True):
            with pytest.raises(ValueError, match=f"^{CLIENT_MSG}$"):
                method(bad)
    lim.allow("x" * 64)                # max length valid


def test_tick_validation():
    lim = Limiter(1, 1)
    for bad in (0, -1, True, False, "2", 1.5, None):
        with pytest.raises(ValueError, match=f"^{TICK_MSG}$"):
            lim.tick(bad)
