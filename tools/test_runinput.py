"""Unit tests for the guarded run-path input helper (tools/runinput.py) (P4.5a).

No API key, no Docker: the helper is pure file I/O over tmp_path files, plus two
integration checks that a malformed meta.json stops run_loop BEFORE any generation
or evaluation. Covers the three guard failures (missing, truncated, syntactically
invalid), the unreadable branch, the case/mcase required-key shape rules, the
baseline and aggregate guards, and a corpus round-trip proving every existing valid
case and mcase still loads unchanged.

  cd tools && python -m pytest test_runinput.py -q -p no:cacheprovider
"""
import json
from pathlib import Path

import pytest

import loop
import mloop
import runinput

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "cases"
MCASES = ROOT / "mcases"


def _corpus_cases():
    return [d for d in sorted(CASES.iterdir()) if (d / "meta.json").is_file()]


def _corpus_mcases():
    return [d for d in sorted(MCASES.iterdir())
            if d.is_dir() and (d / "meta.json").is_file()]


# --------------------------------------------------------------- guarded load

def test_missing_meta_raises_runinputerror_naming_file(tmp_path):
    missing = tmp_path / "meta.json"
    with pytest.raises(runinput.RunInputError) as e:
        runinput.load_case_meta(tmp_path)
    msg = str(e.value)
    assert str(missing) in msg and "not found" in msg


def test_truncated_meta_raises_runinputerror_naming_file(tmp_path):
    p = tmp_path / "meta.json"
    p.write_text('{"case_id": "c", "entry_point": "f"', encoding="utf-8")  # no closing brace
    with pytest.raises(runinput.RunInputError) as e:
        runinput.load_case_meta(tmp_path)
    msg = str(e.value)
    assert str(p) in msg and "not valid JSON" in msg


def test_invalid_json_meta_raises_runinputerror_naming_file(tmp_path):
    p = tmp_path / "meta.json"
    p.write_text("this is not json at all", encoding="utf-8")
    with pytest.raises(runinput.RunInputError) as e:
        runinput.load_mcase_meta(tmp_path)
    msg = str(e.value)
    assert str(p) in msg and "not valid JSON" in msg


def test_unreadable_input_raises_runinputerror_not_oserror(tmp_path):
    # A directory where a file is expected exercises the OSError branch (the file is
    # present in the path sense but cannot be read as a file).
    d = tmp_path / "baseline_metrics.json"
    d.mkdir()
    with pytest.raises(runinput.RunInputError) as e:
        runinput.load_json(d, "baseline_metrics.json")
    assert str(d) in str(e.value)


# --------------------------------------------------------------- shape rules

def test_case_meta_missing_entry_point_fails_naming_key(tmp_path):
    (tmp_path / "meta.json").write_text(
        json.dumps({"case_id": "c", "category": "x"}), encoding="utf-8")
    with pytest.raises(runinput.RunInputError) as e:
        runinput.load_case_meta(tmp_path)
    msg = str(e.value)
    assert "entry_point" in msg and str(tmp_path / "meta.json") in msg


def test_case_meta_missing_case_id_fails_naming_key(tmp_path):
    (tmp_path / "meta.json").write_text(
        json.dumps({"entry_point": "f"}), encoding="utf-8")
    with pytest.raises(runinput.RunInputError) as e:
        runinput.load_case_meta(tmp_path)
    assert "case_id" in str(e.value)


def test_mcase_meta_missing_entry_fails_naming_key(tmp_path):
    (tmp_path / "meta.json").write_text(
        json.dumps({"case_id": "c", "kind": "x"}), encoding="utf-8")
    with pytest.raises(runinput.RunInputError) as e:
        runinput.load_mcase_meta(tmp_path)
    msg = str(e.value)
    assert "entry" in msg and str(tmp_path / "meta.json") in msg


def test_non_object_meta_fails_clearly(tmp_path):
    (tmp_path / "meta.json").write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(runinput.RunInputError) as e:
        runinput.load_case_meta(tmp_path)
    assert "JSON object" in str(e.value)


def test_optional_keys_stay_optional(tmp_path):
    # Exactly the required keys, none of the optional ones: must load unchanged.
    (tmp_path / "meta.json").write_text(
        json.dumps({"case_id": "c", "entry_point": "f"}), encoding="utf-8")
    assert runinput.load_case_meta(tmp_path) == {"case_id": "c", "entry_point": "f"}
    (tmp_path / "meta.json").write_text(
        json.dumps({"case_id": "c", "entry": "E"}), encoding="utf-8")
    assert runinput.load_mcase_meta(tmp_path) == {"case_id": "c", "entry": "E"}


# --------------------------------------------------- baseline / aggregate guard

def test_missing_baseline_raises_clear_error(tmp_path):
    with pytest.raises(runinput.RunInputError) as e:
        runinput.load_json(tmp_path / "baseline_metrics.json", "baseline_metrics.json")
    msg = str(e.value)
    assert "baseline_metrics.json" in msg and "not found" in msg


def test_missing_aggregate_raises_clear_error(tmp_path):
    with pytest.raises(runinput.RunInputError) as e:
        runinput.load_json(tmp_path / "aggregate.json", "aggregate.json")
    msg = str(e.value)
    assert "aggregate.json" in msg and "not found" in msg


# ---------------------------------------- malformed input stops BEFORE the run

def test_case_loop_aborts_before_run_on_missing_key(tmp_path, monkeypatch):
    """A case meta.json missing entry_point stops run_loop at the meta read, before
    any generation or evaluation (the run_dir is never even created)."""
    case = tmp_path / "cases" / "broken"
    case.mkdir(parents=True)
    (case / "meta.json").write_text(json.dumps({"case_id": "broken"}), encoding="utf-8")
    (case / "original.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(loop, "CASES", tmp_path / "cases")
    monkeypatch.setattr(loop, "RUNS", tmp_path / "runs")
    with pytest.raises(runinput.RunInputError) as e:
        loop.run_loop("broken")
    assert "entry_point" in str(e.value)
    assert not (tmp_path / "runs").exists()       # never reached run_dir creation


def test_mcase_loop_aborts_before_run_on_missing_key(tmp_path, monkeypatch):
    """An mcase meta.json missing entry stops mloop.run_loop at the meta read,
    before generation or evaluation."""
    case = tmp_path / "mcases" / "broken"
    case.mkdir(parents=True)
    (case / "meta.json").write_text(json.dumps({"case_id": "broken"}), encoding="utf-8")
    monkeypatch.setattr(mloop, "MCASES", tmp_path / "mcases")
    monkeypatch.setattr(mloop, "RUNS", tmp_path / "runs")
    sentinel = {"called": False}

    def must_not_run(*a, **k):
        sentinel["called"] = True
        raise AssertionError("generation/evaluation reached despite bad meta")

    with pytest.raises(runinput.RunInputError) as e:
        mloop.run_loop("broken", generate=must_not_run, evaluate=must_not_run)
    assert "entry" in str(e.value)
    assert sentinel["called"] is False


# --------------------------------------- every existing valid input still loads

@pytest.mark.parametrize("case_dir", _corpus_cases(), ids=lambda d: d.name)
def test_valid_corpus_case_meta_loads_identically(case_dir):
    raw = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    assert runinput.load_case_meta(case_dir) == raw


@pytest.mark.parametrize("case_dir", _corpus_mcases(), ids=lambda d: d.name)
def test_valid_corpus_mcase_meta_loads_identically(case_dir):
    raw = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    assert runinput.load_mcase_meta(case_dir) == raw
