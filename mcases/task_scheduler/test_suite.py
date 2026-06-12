"""Strict test suite for the task_scheduler unit.

Runs against the unit named by MCASE_UNIT (original|reference, default
original) so the same bar applies to both. Requires PYTHONPATH to include
tools/ (validate_mcase.py sets this).
"""
import os
from pathlib import Path

import pytest
from mdiffer import load_unit

UNIT_DIR = Path(__file__).parent / os.environ.get("MCASE_UNIT", "original")
Scheduler = load_unit(UNIT_DIR).Scheduler

ID_MSG = "job_id must be a non-empty string of at most 64 characters"
PRIORITY_MSG = "priority must be an integer between -10 and 10"
RETRIES_MSG = "retries must be an integer between 0 and 5"


def make():
    return Scheduler()


# ---------------------------------------------------------------- normal

def test_submit_and_run_to_done():
    s = make()
    s.submit("a")
    assert s.status("a") == "queued"
    assert s.next_job() == "a"
    assert s.status("a") == "running"
    s.complete("a")
    assert s.status("a") == "done"


def test_priority_order():
    s = make()
    s.submit("low", priority=-5)
    s.submit("high", priority=5)
    s.submit("mid", priority=0)
    assert s.next_job() == "high"
    assert s.next_job() == "mid"
    assert s.next_job() == "low"


def test_fifo_tie_break_within_priority():
    s = make()
    s.submit("first", priority=3)
    s.submit("second", priority=3)
    s.submit("third", priority=3)
    assert s.next_job() == "first"
    assert s.next_job() == "second"
    assert s.next_job() == "third"


def test_pending_is_pop_order():
    s = make()
    s.submit("b", priority=1)
    s.submit("a", priority=2)
    s.submit("c", priority=1)
    assert s.pending() == ["a", "b", "c"]


def test_retry_requeues_at_back_of_class():
    s = make()
    s.submit("a", priority=0, retries=1)
    s.submit("b", priority=0)
    assert s.next_job() == "a"
    assert s.fail("a") == "requeued"
    assert s.pending() == ["b", "a"]
    assert s.next_job() == "b"


def test_retry_exhaustion_goes_dead():
    s = make()
    s.submit("a", retries=1)
    assert s.next_job() == "a"
    assert s.fail("a") == "requeued"
    assert s.next_job() == "a"
    assert s.fail("a") == "dead"
    assert s.status("a") == "dead"


def test_zero_retries_dead_on_first_fail():
    s = make()
    s.submit("a", retries=0)
    s.next_job()
    assert s.fail("a") == "dead"


# ------------------------------------------------------------ edge/empty

def test_next_job_empty_returns_none():
    s = make()
    assert s.next_job() is None


def test_pending_empty():
    assert make().pending() == []


def test_resubmit_after_terminal_allowed():
    s = make()
    s.submit("a", retries=0)
    s.next_job()
    s.fail("a")
    s.submit("a", priority=1)          # dead -> fresh record
    assert s.status("a") == "queued"
    s2 = make()
    s2.submit("x")
    s2.cancel("x")
    s2.submit("x")
    assert s2.status("x") == "queued"


def test_resubmit_active_rejected():
    s = make()
    s.submit("a")
    with pytest.raises(ValueError, match="^job already active$"):
        s.submit("a")
    s.next_job()
    with pytest.raises(ValueError, match="^job already active$"):
        s.submit("a")


def test_cancel_queued_removes_from_queue():
    s = make()
    s.submit("a")
    s.submit("b")
    s.cancel("a")
    assert s.status("a") == "cancelled"
    assert s.pending() == ["b"]
    assert s.next_job() == "b"


def test_cancel_running_allowed():
    s = make()
    s.submit("a")
    s.next_job()
    s.cancel("a")
    assert s.status("a") == "cancelled"


def test_cancel_terminal_rejected():
    s = make()
    s.submit("a")
    s.next_job()
    s.complete("a")
    with pytest.raises(ValueError, match="^job not active$"):
        s.cancel("a")


def test_complete_and_fail_require_running():
    s = make()
    s.submit("a")
    with pytest.raises(ValueError, match="^job not running$"):
        s.complete("a")
    with pytest.raises(ValueError, match="^job not running$"):
        s.fail("a")


def test_unknown_ids_raise_keyerror():
    s = make()
    for method in (s.complete, s.fail, s.cancel, s.status):
        with pytest.raises(KeyError):
            method("ghost")


def test_stats_counters():
    s = make()
    s.submit("a", retries=1)
    s.submit("b")
    s.submit("c")
    s.next_job(); s.fail("a")          # requeued
    s.next_job(); s.complete("b")      # b ran (a went to back of class)
    s.cancel("c")
    s.next_job(); s.fail("a")          # dead
    assert s.stats() == {"submitted": 3, "completed": 1, "failed": 2,
                         "retried": 1, "cancelled": 1, "dead": 1,
                         "queued": 0, "running": 0}


# ------------------------------------------------- boundary / validation

def test_id_boundaries():
    s = make()
    s.submit("x" * 64)                 # max length valid
    for bad in ("", "x" * 65, 7, None, ["a"]):
        with pytest.raises(ValueError, match=f"^{ID_MSG}$"):
            s.submit(bad)


def test_id_validation_on_every_id_method():
    s = make()
    for method in (s.complete, s.fail, s.cancel, s.status):
        for bad in ("", "x" * 65, 7):
            with pytest.raises(ValueError, match=f"^{ID_MSG}$"):
                method(bad)


def test_priority_boundaries():
    s = make()
    s.submit("lo", priority=-10)
    s.submit("hi", priority=10)
    for bad in (-11, 11, True, False, "5", 1.5, None):
        with pytest.raises(ValueError, match=f"^{PRIORITY_MSG}$"):
            s.submit("p", priority=bad)


def test_retries_boundaries():
    s = make()
    s.submit("r0", retries=0)
    s.submit("r5", retries=5)
    for bad in (-1, 6, True, "2", None):
        with pytest.raises(ValueError, match=f"^{RETRIES_MSG}$"):
            s.submit("r", retries=bad)


def test_validation_precedes_existence():
    s = make()
    with pytest.raises(ValueError, match=f"^{ID_MSG}$"):
        s.status("")                   # ValueError, not KeyError
