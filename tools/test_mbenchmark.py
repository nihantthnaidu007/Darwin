"""Offline tests for the multi-file benchmark harness (mrun_summary + mbenchmark).

These run with NO API key and NO Docker: every test is driven by synthetic
run.json fixtures and synthetic summaries. The real mloop is never called; the
per-case loop call is injected. The baseline is a synthetic mcase whose
mcases/ root is monkeypatched in, so nothing depends on the real cases either.

  cd tools && python -m pytest test_mbenchmark.py -q -p no:cacheprovider
"""
import json
from pathlib import Path

import mbenchmark
import mrun_summary

# --- synthetic multi-file baseline (the {aggregate, per_file} shape mloop logs) ----
# Multi-file baseline: original["aggregate"] and reference["aggregate"]; key is
# "reference", not "reference_floor". Values are arbitrary but carry every metric
# the per-metric cost basis reads (all WEIGHTS metrics that live in the aggregate).
_ORIG = {"file_count": 5, "cyclomatic_total": 100, "cyclomatic_max": 12,
         "logical_loc": 200, "source_loc": 200, "dependency_count": 4,
         "dependencies": [], "dead_code_count": 10, "max_nesting_depth": 8}
_FLOOR = {"file_count": 2, "cyclomatic_total": 40, "cyclomatic_max": 4,
          "logical_loc": 70, "source_loc": 73, "dependency_count": 0,
          "dependencies": [], "dead_code_count": 6, "max_nesting_depth": 3}
# A near-floor candidate aggregate (one-shot's gen 1) and two improving steps
# (load-bearing's gen 1 then gen 2).
_AGG_NEAR = {"file_count": 2, "cyclomatic_total": 45, "cyclomatic_max": 4,
             "logical_loc": 72, "source_loc": 73, "dependency_count": 0,
             "dependencies": [], "dead_code_count": 6, "max_nesting_depth": 3}
_AGG_STEP1 = {"file_count": 4, "cyclomatic_total": 70, "cyclomatic_max": 8,
              "logical_loc": 120, "source_loc": 120, "dependency_count": 2,
              "dependencies": [], "dead_code_count": 8, "max_nesting_depth": 5}
_AGG_STEP2 = {"file_count": 3, "cyclomatic_total": 50, "cyclomatic_max": 6,
              "logical_loc": 90, "source_loc": 90, "dependency_count": 1,
              "dependencies": [], "dead_code_count": 7, "max_nesting_depth": 4}

_BASELINE = {"original": {"aggregate": _ORIG, "per_file": {}},
             "reference": {"aggregate": _FLOOR, "per_file": {}}}


def _basket(agg):
    return {"aggregate": agg, "per_file": {}}


def _rec(gen, verdict, *, wc=None, agg=None, improved=False, flags=None):
    """One trace record in mloop's shape. A baseline/scored record carries the full
    {aggregate, per_file} metric basket; a record with no metrics omits it."""
    rec = {"generation": gen, "verdict": verdict, "is_improvement": improved,
           "feedback_given": "", "candidate_dir": f"gen_{gen:02d}"}
    if agg is not None:
        rec["metrics"] = _basket(agg)
        rec["weighted_cost"] = wc
        rec["flags"] = flags or []
    return rec


def _write_run(run_dir, *, case="fakecase", trace, best_wc, base_wc=1.0,
               improved, returned, generations,
               tokens_in=1000, tokens_out=2000, cost=0.05):
    """Write a synthetic run.json into run_dir in mloop's exact summary shape."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    run = {
        "case": case, "model": "test-model",
        "config": {"cap": 5, "plateau_limit": 2},
        "baseline_weighted_cost": base_wc, "best_weighted_cost": best_wc,
        "improved_over_baseline": improved, "returned": returned,
        "best_dir": str(run_dir / "best"), "halted": None,
        "generations": generations,
        "total_input_tokens": tokens_in, "total_output_tokens": tokens_out,
        "total_cost_usd": cost, "trace": trace,
    }
    (run_dir / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    return run_dir


def _patch_mcases(monkeypatch, tmp_path, case="fakecase"):
    """A temp mcases/ root holding one synthetic, complete-enough mcase, patched
    into both modules that read it. No Docker, no real case data."""
    root = tmp_path / "mcases"
    cdir = root / case
    cdir.mkdir(parents=True)
    (cdir / "baseline_metrics.json").write_text(json.dumps(_BASELINE), encoding="utf-8")
    (cdir / "meta.json").write_text(
        json.dumps({"case_id": case, "entry": "Synthetic",
                    "kind": "synthetic-unit", "difficulty": "medium"}), encoding="utf-8")
    monkeypatch.setattr(mrun_summary, "MCASES", root)
    monkeypatch.setattr(mbenchmark, "MCASES", root)
    return root


# ---------------------------------------------------------------- summarize_mrun

def test_one_shot_trace(monkeypatch, tmp_path):
    """Generation 1 is the best: best_generation == 1 and no feedback gain."""
    _patch_mcases(monkeypatch, tmp_path)
    trace = [
        _rec(0, "baseline", wc=1.0, agg=_ORIG, improved=False),
        _rec(1, "scored", wc=0.2, agg=_AGG_NEAR, improved=True),
    ]
    run_dir = _write_run(tmp_path / "run", trace=trace, best_wc=0.2,
                         improved=True, returned="best-candidate", generations=1)
    s = mrun_summary.summarize_mrun(run_dir)

    assert s["improved_over_baseline"] is True
    assert s["best_generation"] == 1
    assert s["first_scored_generation"] == 1
    assert s["feedback_gain_pp"] == 0.0          # gen 1 IS the best -> no later gain
    assert s["structural_changes_from_first"] == []
    assert s["bloat_removed_pct"] == 80.0        # (1 - 0.2) * 100, read from the log


def test_load_bearing_trace(monkeypatch, tmp_path):
    """A later generation improves on gen 1: best_generation >= 2, a positive
    feedback_gain_pp, and the exact structural metrics feedback moved."""
    _patch_mcases(monkeypatch, tmp_path)
    trace = [
        _rec(0, "baseline", wc=1.0, agg=_ORIG, improved=False),
        _rec(1, "scored", wc=0.5, agg=_AGG_STEP1, improved=True),
        _rec(2, "scored", wc=0.3, agg=_AGG_STEP2, improved=True),
    ]
    run_dir = _write_run(tmp_path / "run", trace=trace, best_wc=0.3,
                         improved=True, returned="best-candidate", generations=2)
    s = mrun_summary.summarize_mrun(run_dir)

    assert s["best_generation"] == 2
    assert s["first_scored_generation"] == 1
    assert s["first_pass_bloat_removed_pct"] == 50.0   # gen 1 alone: (1 - 0.5)*100
    assert s["feedback_gain_pp"] == 20.0               # later gens added (0.5 - 0.3)*100
    assert s["feedback_gain_pp"] > 0
    # Exactly the metrics that differ between gen 1 (first scored) and gen 2 (best).
    changes = {c["metric"]: (c["first_pass"], c["best"])
               for c in s["structural_changes_from_first"]}
    assert changes == {
        "cyclomatic_total": (70, 50), "logical_loc": (120, 90),
        "max_nesting_depth": (5, 4), "dependency_count": (2, 1),
        "dead_code_count": (8, 7), "cyclomatic_max": (8, 6),
    }


def test_baseline_kept_trace(monkeypatch, tmp_path):
    """Nothing beat the original (a scored gen exists but did not improve):
    best_generation == 0 and NO feedback attribution."""
    _patch_mcases(monkeypatch, tmp_path)
    trace = [
        _rec(0, "baseline", wc=1.0, agg=_ORIG, improved=False),
        _rec(1, "scored", wc=1.0, agg=_ORIG, improved=False),  # scored, did not beat baseline
    ]
    run_dir = _write_run(tmp_path / "run", trace=trace, best_wc=1.0,
                         improved=False, returned="baseline-original", generations=1)
    s = mrun_summary.summarize_mrun(run_dir)

    assert s["improved_over_baseline"] is False
    assert s["best_generation"] == 0
    # A scored generation exists, but the baseline was kept -> feedback moved nothing.
    assert s["feedback_gain_pp"] is None
    assert s["structural_changes_from_first"] == []


def test_per_metric_uses_imported_cost_basis(monkeypatch, tmp_path):
    """The per-metric norm_cost is the SAME multi-file cost mevaluator computes
    (0.0 at the floor, 1.0 at the original) -- not a re-implemented scale."""
    _patch_mcases(monkeypatch, tmp_path)
    # A candidate sitting exactly at the floor must report norm_cost 0.0 everywhere
    # the case gives a signal, and at_or_below_floor True.
    trace = [
        _rec(0, "baseline", wc=1.0, agg=_ORIG, improved=False),
        _rec(1, "scored", wc=0.0, agg=_FLOOR, improved=True),
    ]
    run_dir = _write_run(tmp_path / "run", trace=trace, best_wc=0.0,
                         improved=True, returned="best-candidate", generations=1)
    s = mrun_summary.summarize_mrun(run_dir)
    assert s["floor_reached"] is True
    for pm in s["per_metric"]:
        if pm["norm_cost"] is not None:           # dependency_count gives no signal here
            assert pm["norm_cost"] == 0.0
            assert pm["at_or_below_floor"] is True


# ---------------------------------------------------------------- aggregate

def _fake_summary(case, *, improved, best_gen, first_scored=1,
                  first_pass=90.0, bloat=95.0, gain=None, changes=None,
                  kind="synthetic-unit", difficulty="medium",
                  cost=0.05, tin=1000, tout=2000, wc=0.05):
    """A summarize_mrun-shaped row with every field aggregate() reads."""
    return {
        "case": case, "kind": kind, "difficulty": difficulty,
        "verdict": ("improved (best candidate returned)" if improved
                    else "no improvement (baseline original returned)"),
        "improved_over_baseline": improved,
        "best_weighted_cost": wc, "bloat_removed_pct": bloat,
        "first_pass_bloat_removed_pct": first_pass,
        "feedback_gain_pp": gain,
        "generations_attempted": best_gen if best_gen else 1,
        "best_generation": best_gen, "first_scored_generation": first_scored,
        "floor_reached": False,
        "total_cost_usd": cost, "total_input_tokens": tin, "total_output_tokens": tout,
        "best_flags": [], "halted": None,
        "structural_changes_from_first": changes or [],
        "per_metric": [], "run_dir": f"/runs/{case}",
    }


def test_aggregate_counts():
    """improved / one-shot / needed-feedback counts and totals over synthetic rows."""
    changes = [{"metric": "logical_loc", "first_pass": 120, "best": 90}]
    rows = [
        _fake_summary("c1", improved=True, best_gen=1),                       # one-shot
        _fake_summary("c2", improved=True, best_gen=2, first_pass=50.0,       # needed feedback
                      bloat=70.0, gain=15.0, changes=changes),
        _fake_summary("c3", improved=True, best_gen=1),                       # one-shot
        _fake_summary("c4", improved=False, best_gen=0, first_scored=None,    # baseline kept
                      bloat=0.0),
    ]
    agg = mbenchmark.aggregate(rows, "test-model", 5, 2)

    assert agg["n_cases"] == 4
    assert agg["improved"] == 3
    assert agg["baseline_returned"] == 1
    assert agg["one_shot"] == 2
    assert agg["needed_feedback"] == 1
    assert agg["feedback_load_bearing"] is True
    # The needed-feedback case carries its magnitude and the structural change.
    nf = agg["needed_feedback_cases"]
    assert len(nf) == 1 and nf[0]["case"] == "c2"
    assert nf[0]["feedback_gain_pp"] == 15.0
    assert nf[0]["first_pass_bloat_removed_pct"] == 50.0
    assert nf[0]["structural_changes_from_first"] == changes
    # Totals are summed straight from the rows (not recomputed).
    assert agg["total_cost_usd"] == round(4 * 0.05, 6)
    assert agg["total_input_tokens"] == 4000
    assert agg["total_output_tokens"] == 8000


def test_aggregate_no_feedback_when_all_one_shot():
    rows = [_fake_summary("c1", improved=True, best_gen=1),
            _fake_summary("c2", improved=True, best_gen=1)]
    agg = mbenchmark.aggregate(rows, "test-model", 5, 2)
    assert agg["improved"] == 2 and agg["one_shot"] == 2
    assert agg["needed_feedback"] == 0
    assert agg["feedback_load_bearing"] is False
    assert agg["needed_feedback_cases"] == []


# ------------------------------------------------ run_benchmark + write_aggregate

def test_run_benchmark_with_fake_loop_writes_aggregate(monkeypatch, tmp_path):
    """run_benchmark with an INJECTED fake run_loop (no API key, no Docker) reads
    the loop's own logs back through summarize_mrun and write_aggregate produces a
    maggregate.json of the correct shape."""
    _patch_mcases(monkeypatch, tmp_path, case="fakecase")
    runs_root = tmp_path / "runs"

    def fake_run_loop(case, cap, plateau, model):
        # The loop writes its OWN run.json; the harness must read THAT, not a
        # passed-in summary. Here: a load-bearing two-generation trace.
        run_dir = _write_run(
            runs_root / case,
            case=case,
            trace=[
                _rec(0, "baseline", wc=1.0, agg=_ORIG, improved=False),
                _rec(1, "scored", wc=0.5, agg=_AGG_STEP1, improved=True),
                _rec(2, "scored", wc=0.3, agg=_AGG_STEP2, improved=True),
            ],
            best_wc=0.3, improved=True, returned="best-candidate", generations=2,
            cost=0.07, tokens_in=1500, tokens_out=3000)
        return {"case": case}, run_dir       # summary is ignored; logs are the truth

    rows = mbenchmark.run_benchmark(["fakecase"], 5, 2, "test-model",
                                    run_loop=fake_run_loop)
    assert len(rows) == 1
    assert rows[0]["kind"] == "synthetic-unit" and rows[0]["difficulty"] == "medium"
    assert rows[0]["best_generation"] == 2          # came from the loop's logged trace

    agg = mbenchmark.aggregate(rows, "test-model", 5, 2)
    path = mbenchmark.write_aggregate(agg, tmp_path / "reports")
    assert path.name == "maggregate.json" and path.exists()

    written = json.loads(path.read_text(encoding="utf-8"))
    for key in ("model", "config", "n_cases", "improved", "baseline_returned",
                "one_shot", "needed_feedback", "needed_feedback_cases",
                "feedback_load_bearing", "total_cost_usd", "total_input_tokens",
                "total_output_tokens", "by_kind", "by_difficulty", "cases"):
        assert key in written, f"missing top-level key {key!r}"
    assert written["n_cases"] == 1
    assert written["improved"] == 1
    assert written["needed_feedback"] == 1
    assert written["feedback_load_bearing"] is True
    assert written["total_cost_usd"] == 0.07
    assert written["cases"][0]["case"] == "fakecase"
    assert written["cases"][0]["kind"] == "synthetic-unit"
    assert written["by_difficulty"]["medium"]["n"] == 1
