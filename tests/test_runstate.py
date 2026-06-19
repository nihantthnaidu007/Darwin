"""Unit tests for the shared run-state checkpoint helper (src/darwin/runstate.py).

No API key, no Docker, no real cases: the helper is pure file I/O over a tmp_path
JSONL file. Covers the format round-trip, clearing prior state, last-write-wins,
and the crash-tolerance requirement that a partial trailing record is ignored.

  cd tools && python -m pytest test_runstate.py -q -p no:cacheprovider
"""

import json

import pytest

from darwin import runstate


def test_completed_empty_when_no_file(tmp_path):
    st = runstate.RunState(tmp_path / "state.jsonl")
    assert st.completed() == {}


def test_append_and_completed_roundtrip(tmp_path):
    st = runstate.RunState(tmp_path / "state.jsonl")
    r1 = {
        "case": "c1",
        "verdict": "improved",
        "bloat_removed_pct": 80.0,
        "per_metric": [],
        "nested": {"a": 1, "b": [1, 2, 3]},
    }
    r2 = {"case": "c2", "verdict": "baseline", "bloat_removed_pct": 0.0}
    st.append("c1", r1)
    st.append("c2", r2)
    done = st.completed()
    assert set(done) == {"c1", "c2"}
    assert done["c1"] == r1  # faithful round-trip, including nesting/floats
    assert done["c2"] == r2
    # Human-readable: one JSON object per line, each carrying case + result.
    lines = (tmp_path / "state.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"case": "c1", "result": r1}


def test_clear_removes_prior_state(tmp_path):
    path = tmp_path / "state.jsonl"
    st = runstate.RunState(path)
    st.append("c1", {"x": 1})
    assert st.completed() == {"c1": {"x": 1}}
    st.clear()
    assert not path.exists()
    assert st.completed() == {}  # a fresh run sees nothing stale


def test_clear_is_safe_when_absent(tmp_path):
    st = runstate.RunState(tmp_path / "nope.jsonl")
    st.clear()  # no error when there is nothing to clear
    assert st.completed() == {}


def test_last_write_wins(tmp_path):
    st = runstate.RunState(tmp_path / "state.jsonl")
    st.append("c1", {"v": "first"})
    st.append("c1", {"v": "second"})  # e.g. a re-run after a partial write
    assert st.completed() == {"c1": {"v": "second"}}


def test_partial_trailing_record_is_tolerated(tmp_path):
    path = tmp_path / "state.jsonl"
    st = runstate.RunState(path)
    st.append("c1", {"v": 1})
    st.append("c2", {"v": 2})
    # Simulate a crash mid-write of a third record: a trailing line with no
    # newline terminator (and not even valid JSON yet).
    with open(path, "a", encoding="utf-8") as f:
        f.write('{"case": "c3", "result": {"v": 3')  # truncated, no closing/newline
    done = st.completed()
    assert set(done) == {"c1", "c2"}  # only the two complete records
    assert "c3" not in done  # the partial case is treated as not done


def test_complete_record_then_partial_trailing(tmp_path):
    path = tmp_path / "state.jsonl"
    st = runstate.RunState(path)
    st.append("c1", {"v": 1})
    # A complete record whose newline was written, then a torn final line.
    with open(path, "a", encoding="utf-8") as f:
        f.write('{"case": "c2", "result": {"v": 2}}\n')  # complete (has newline)
        f.write('{"case": "c3", "resul')  # partial, no newline
    done = st.completed()
    assert set(done) == {"c1", "c2"}
    assert done["c2"] == {"v": 2}


# ---------------------------------------------- config record (P4.2.2)


def test_start_records_config_and_completed_skips_it(tmp_path):
    path = tmp_path / "state.jsonl"
    st = runstate.RunState(path)
    cfg = runstate.run_config("claude-opus-4-8", 5, 2)
    st.start(cfg)
    st.append("c1", {"v": 1})
    # Config is the leading, human-readable record and reads back faithfully.
    assert st.read_config() == {"model": "claude-opus-4-8", "cap": 5, "plateau": 2}
    lines = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0]) == {"config": cfg}
    # The config record is NOT counted as a completed case.
    assert st.completed() == {"c1": {"v": 1}}


def test_start_overwrites_prior_state_and_config(tmp_path):
    st = runstate.RunState(tmp_path / "state.jsonl")
    st.start(runstate.run_config("m1", 5, 2))
    st.append("old", {"v": 1})
    st.start(runstate.run_config("m2", 7, 3))  # a second fresh run
    assert st.read_config() == {"model": "m2", "cap": 7, "plateau": 3}
    assert st.completed() == {}  # prior cases cleared


def test_read_config_none_when_absent(tmp_path):
    st = runstate.RunState(tmp_path / "nope.jsonl")
    assert st.read_config() is None


def test_resume_matching_config_returns_completed(tmp_path):
    st = runstate.RunState(tmp_path / "state.jsonl")
    st.start(runstate.run_config("m", 5, 2))
    st.append("c1", {"v": 1})
    assert st.resume(runstate.run_config("m", 5, 2)) == {"c1": {"v": 1}}


@pytest.mark.parametrize(
    "field, current",
    [
        ("model", runstate.run_config("other-model", 5, 2)),
        ("cap", runstate.run_config("m", 9, 2)),
        ("plateau", runstate.run_config("m", 5, 4)),
    ],
)
def test_resume_config_mismatch_raises_naming_field(tmp_path, field, current):
    st = runstate.RunState(tmp_path / "state.jsonl")
    st.start(runstate.run_config("m", 5, 2))
    st.append("c1", {"v": 1})
    with pytest.raises(runstate.ConfigMismatchError) as ei:
        st.resume(current)
    msg = str(ei.value)
    assert field in msg  # names the differing field
    assert "fresh run" in msg  # actionable: states the escape
