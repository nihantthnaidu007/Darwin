"""Orchestrator-level checkpoint/resume tests for BOTH benchmarks (P4.2).

No API key, no Docker, no real cases: each test injects a fake run_loop and
monkeypatches the per-case summary + meta lookups, so the focus is purely the
checkpoint orchestration (clear / persist / skip / resume / aggregate-union) that
this phase added. Summary parsing itself is covered by test_mbenchmark.py.

The same four behaviors are asserted for benchmark.py and mbenchmark.py:
- happy-path equivalence: a complete fresh checkpointed run's aggregate is
  byte-identical to the non-checkpointed aggregate (the regression guard);
- interrupted run + resume: a crash persists only the completed cases, resume
  skips them and runs the rest, and the union aggregate covers all cases, no dupes;
- a resumed run's aggregate equals a full fresh run's aggregate;
- a fresh run clears stale state and never skips a case from a stale prior run.

  cd tools && python -m pytest test_checkpoint.py -q -p no:cacheprovider
"""
import json

import pytest

import benchmark
import mbenchmark
import runstate

# (module, summarize-attr to stub, the grouping key its aggregate reads)
_ORCH = {
    "benchmark": (benchmark, "summarize_run", "category"),
    "mbenchmark": (mbenchmark, "summarize_mrun", "kind"),
}


def _row(case, *, improved=True, best_gen=1, bloat=90.0):
    """A summarize_run/summarize_mrun-shaped row with every field aggregate() reads
    (the grouping key + difficulty are added by run_benchmark from _case_meta)."""
    return {
        "case": case,
        "improved_over_baseline": improved,
        "best_generation": best_gen,
        "first_scored_generation": 1,
        "first_pass_bloat_removed_pct": bloat,
        "bloat_removed_pct": bloat,
        "feedback_gain_pp": 0.0,
        "structural_changes_from_first": [],
        "verdict": "improved" if improved else "baseline-kept",
        "best_weighted_cost": 0.1,
        "generations_attempted": best_gen or 1,
        "floor_reached": False,
        "total_cost_usd": 0.05,
        "total_input_tokens": 1000,
        "total_output_tokens": 2000,
        "best_flags": [],
        "halted": None,
        "per_metric": [],
        "run_dir": f"/runs/{case}",
    }


def _patch(monkeypatch, name):
    """Stub the summary (reads run_dir = the case name) and the meta lookup, so a
    fake run_loop returning (None, case) drives the whole orchestration offline.
    Returns the orchestrator module."""
    mod, summ_attr, _ = _ORCH[name]
    monkeypatch.setattr(mod, summ_attr, lambda run_dir: _row(str(run_dir)))
    monkeypatch.setattr(mod, "_case_meta", lambda case: ("grp", "med"))
    return mod


def _recording_loop(calls):
    def loop(case, cap, plateau, model):
        calls.append(case)
        return None, case            # run_dir == case name; the stub reads it back
    return loop


# ------------------------------------------------- happy-path equivalence

@pytest.mark.parametrize("name", ["benchmark", "mbenchmark"])
def test_fresh_checkpointed_aggregate_equals_uncheckpointed(monkeypatch, tmp_path, name):
    mod = _patch(monkeypatch, name)
    cases = ["a", "b", "c"]

    rows_plain = mod.run_benchmark(cases, 5, 2, "m",
                                   run_loop=_recording_loop([]), state=None)
    agg_plain = mod.aggregate(rows_plain, "m", 5, 2)

    st = runstate.RunState(tmp_path / "state.jsonl")
    rows_ckpt = mod.run_benchmark(cases, 5, 2, "m",
                                  run_loop=_recording_loop([]), state=st, resume=False)
    agg_ckpt = mod.aggregate(rows_ckpt, "m", 5, 2)

    # Byte-identical aggregate: checkpointing is additive scratch only.
    assert json.dumps(agg_ckpt, sort_keys=True) == json.dumps(agg_plain, sort_keys=True)
    # And every case was persisted as it completed.
    assert set(st.completed()) == set(cases)


# ------------------------------------------- interrupted run + resume

@pytest.mark.parametrize("name", ["benchmark", "mbenchmark"])
def test_interrupted_then_resume(monkeypatch, tmp_path, name):
    mod = _patch(monkeypatch, name)
    cases = ["a", "b", "c"]
    st = runstate.RunState(tmp_path / "state.jsonl")

    # Pass 1: crash partway through (on the 2nd case).
    calls1 = []
    def crashing_loop(case, cap, plateau, model):
        calls1.append(case)
        if case == "b":
            raise RuntimeError("simulated crash mid-run")
        return None, case
    with pytest.raises(RuntimeError):
        mod.run_benchmark(cases, 5, 2, "m", run_loop=crashing_loop, state=st, resume=False)
    assert calls1 == ["a", "b"]                   # reached b, then crashed
    assert set(st.completed()) == {"a"}           # only the completed case persisted

    # Pass 2: resume. Completed cases are skipped; only the rest run.
    calls2 = []
    rows = mod.run_benchmark(cases, 5, 2, "m",
                             run_loop=_recording_loop(calls2), state=st, resume=True)
    assert calls2 == ["b", "c"]                   # 'a' not re-run; 'b','c' completed
    got = [r["case"] for r in rows]
    assert got == ["a", "b", "c"]                 # union, corpus order
    assert len(got) == len(set(got))              # no duplicates
    assert set(st.completed()) == {"a", "b", "c"}

    # The resumed aggregate equals a full fresh run's aggregate over the same corpus.
    st_full = runstate.RunState(tmp_path / "state_full.jsonl")
    rows_full = mod.run_benchmark(cases, 5, 2, "m",
                                  run_loop=_recording_loop([]), state=st_full, resume=False)
    assert json.dumps(mod.aggregate(rows, "m", 5, 2), sort_keys=True) == \
           json.dumps(mod.aggregate(rows_full, "m", 5, 2), sort_keys=True)


# ----------------------------------------------- fresh run clears stale state

@pytest.mark.parametrize("name", ["benchmark", "mbenchmark"])
def test_fresh_run_clears_stale_state(monkeypatch, tmp_path, name):
    mod = _patch(monkeypatch, name)
    st = runstate.RunState(tmp_path / "state.jsonl")
    # Stale state from a previous run: a case no longer in the corpus, plus one
    # that IS in the new corpus (a fresh run must NOT skip it).
    st.append("stale_old", _row("stale_old"))
    st.append("a", _row("a"))

    calls = []
    cases = ["a", "b"]
    rows = mod.run_benchmark(cases, 5, 2, "m",
                             run_loop=_recording_loop(calls), state=st, resume=False)

    assert calls == ["a", "b"]                    # fresh run ran every case, skipped none
    assert [r["case"] for r in rows] == ["a", "b"]
    assert set(st.completed()) == {"a", "b"}      # stale_old gone; state rewritten clean


# ------------------------------------- resume config mismatch (fail closed, P4.2.2)

@pytest.mark.parametrize("name", ["benchmark", "mbenchmark"])
@pytest.mark.parametrize("field, cap, plateau, model", [
    ("model", 5, 2, "changed-model"),
    ("cap", 9, 2, "base-model"),
    ("plateau", 5, 4, "base-model"),
])
def test_resume_config_mismatch_refused(monkeypatch, tmp_path, name,
                                        field, cap, plateau, model):
    mod = _patch(monkeypatch, name)
    cases = ["a", "b"]
    st = runstate.RunState(tmp_path / "state.jsonl")
    # Fresh run with the base config records {model: base-model, cap: 5, plateau: 2}.
    mod.run_benchmark(cases, 5, 2, "base-model",
                      run_loop=_recording_loop([]), state=st, resume=False)

    # Resume with exactly one field changed -> fail closed BEFORE running any case.
    calls = []
    with pytest.raises(runstate.ConfigMismatchError) as ei:
        mod.run_benchmark(cases, cap, plateau, model,
                          run_loop=_recording_loop(calls), state=st, resume=True)
    assert field in str(ei.value)                 # names the differing field
    assert calls == []                            # no case ran -> no mixed-config aggregate
    assert set(st.completed()) == {"a", "b"}      # state untouched by the refused resume


@pytest.mark.parametrize("name", ["benchmark", "mbenchmark"])
def test_resume_matching_config_proceeds(monkeypatch, tmp_path, name):
    mod = _patch(monkeypatch, name)
    st = runstate.RunState(tmp_path / "state.jsonl")
    # A fresh run of a subset leaves partial state under config {m, 5, 2}.
    mod.run_benchmark(["a"], 5, 2, "m", run_loop=_recording_loop([]),
                      state=st, resume=False)
    # Resume the full corpus with the SAME config -> 'a' skipped, the rest run.
    calls = []
    rows = mod.run_benchmark(["a", "b", "c"], 5, 2, "m",
                             run_loop=_recording_loop(calls), state=st, resume=True)
    assert calls == ["b", "c"]
    assert [r["case"] for r in rows] == ["a", "b", "c"]
