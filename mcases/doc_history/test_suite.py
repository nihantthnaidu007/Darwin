"""Strict test suite for the doc_history unit (MCASE_UNIT selects the unit)."""
import os
from pathlib import Path

import pytest
from mdiffer import load_unit

UNIT_DIR = Path(__file__).parent / os.environ.get("MCASE_UNIT", "original")
DocStore = load_unit(UNIT_DIR).DocStore

HISTORY_MSG = "max_history must be an integer between 1 and 256"
FIELD_MSG = "field must be a non-empty string of at most 64 characters"


def make(cap=10):
    return DocStore(cap)


# ---------------------------------------------------------------- normal

def test_set_get_fields_order():
    d = make()
    d.set("a", 1)
    d.set("b", 2)
    d.set("a", 3)                       # overwrite keeps position
    assert d.get("a") == 3
    assert d.fields() == ["a", "b"]


def test_remove_then_reinsert_at_end():
    d = make()
    d.set("a", 1); d.set("b", 2); d.set("c", 3)
    assert d.remove("b") is True
    assert d.fields() == ["a", "c"]
    d.set("b", 9)
    assert d.fields() == ["a", "c", "b"]


def test_undo_set_created_deletes():
    d = make()
    d.set("a", 1)
    assert d.undo() is True
    assert d.fields() == []
    with pytest.raises(KeyError):
        d.get("a")


def test_undo_overwrite_restores_in_place():
    d = make()
    d.set("a", 1); d.set("b", 2); d.set("a", 9)
    assert d.undo() is True
    assert d.get("a") == 1
    assert d.fields() == ["a", "b"]     # position kept


def test_undo_remove_reinserts_at_end():
    d = make()
    d.set("a", 1); d.set("b", 2); d.set("c", 3)
    d.remove("b")
    assert d.undo() is True
    assert d.get("b") == 2
    assert d.fields() == ["a", "c", "b"]   # documented: end, not original slot


def test_redo_replays():
    d = make()
    d.set("a", 1); d.set("a", 2)
    d.undo()
    assert d.get("a") == 1
    assert d.redo() is True
    assert d.get("a") == 2


def test_undo_redo_chain_round_trip():
    d = make()
    d.set("a", 1); d.set("b", 2); d.remove("a"); d.set("c", 3)
    for _ in range(4):
        assert d.undo() is True
    assert d.undo() is False
    assert d.fields() == []
    for _ in range(4):
        assert d.redo() is True
    assert d.redo() is False
    assert d.fields() == ["b", "c"]
    assert d.get("b") == 2 and d.get("c") == 3


def test_new_set_clears_redo():
    d = make()
    d.set("a", 1); d.set("a", 2)
    d.undo()
    d.set("a", 5)                       # clears redo
    assert d.redo() is False
    assert d.get("a") == 5


def test_noop_remove_does_not_clear_redo():
    d = make()
    d.set("a", 1)
    d.undo()
    assert d.remove("ghost") is False   # full no-op
    assert d.redo() is True             # redo survived
    assert d.get("a") == 1


def test_same_value_set_is_still_a_mutation():
    d = make()
    d.set("a", 1)
    d.undo()
    d.set("b", 2)
    d.set("b", 2)                       # same value: still recorded
    assert d.depth() == {"undo": 2, "redo": 0}
    assert d.undo() is True and d.get("b") == 2
    assert d.undo() is True and d.fields() == []


# ----------------------------------------------------- deep state: the cap

def test_history_cap_drops_oldest():
    d = make(3)
    for i in range(5):
        d.set(f"f{i}", i)
    assert d.depth()["undo"] == 3
    assert [d.undo() for _ in range(4)] == [True, True, True, False]
    assert d.fields() == ["f0", "f1"]   # two oldest sets are un-undoable


def test_cap_exactly_one():
    d = make(1)
    d.set("a", 1); d.set("b", 2)
    assert d.undo() is True
    assert d.undo() is False
    assert d.fields() == ["a"]


# ------------------------------------------------------------ edge/empty

def test_empty_state():
    d = make()
    assert d.fields() == []
    assert d.undo() is False
    assert d.redo() is False
    assert d.depth() == {"undo": 0, "redo": 0}
    assert d.stats() == {"sets": 0, "removes": 0, "undos": 0, "redos": 0,
                         "fields": 0}


def test_failed_undo_redo_do_not_count():
    d = make()
    d.undo(); d.redo()
    assert d.stats()["undos"] == 0
    assert d.stats()["redos"] == 0


def test_stats_counts_successful_mutations_only():
    d = make()
    d.set("a", 1)
    d.remove("ghost")                   # False: not counted
    d.remove("a")                       # True: counted
    d.undo(); d.redo()
    assert d.stats() == {"sets": 1, "removes": 1, "undos": 1, "redos": 1,
                         "fields": 0}


def test_get_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        make().get("ghost")


# ------------------------------------------------- boundary / validation

def test_constructor_boundaries():
    DocStore(1)
    DocStore(256)
    for bad in (0, 257, True, False, "5", 1.5, None):
        with pytest.raises(ValueError, match=f"^{HISTORY_MSG}$"):
            DocStore(bad)


def test_field_validation_on_every_field_method():
    d = make()
    for method in (lambda f: d.set(f, 1), d.remove, d.get):
        for bad in ("", "x" * 65, 7, None, True):
            with pytest.raises(ValueError, match=f"^{FIELD_MSG}$"):
                method(bad)
    d.set("x" * 64, 1)                  # max length valid
    assert d.get("x" * 64) == 1
