"""Tests for the multi-file variance harness (P5.3a). NO API key, NO Docker, NO
model call: derive is exercised on synthetic maggregate.json snapshot fixtures, and
the run orchestration is exercised with a STUBBED runner that writes a fixture
snapshot instead of calling the model.

  cd tools && python -m pytest test_variance_harness.py -q -p no:cacheprovider
"""

import json
from pathlib import Path

from darwin import mbenchmark
from darwin import variance_harness as vh


# ----------------------------------------------------------- fixtures


def _case(
    case,
    best_gen,
    gen1,
    best_bloat,
    gain,
    *,
    improved=True,
    kind="synthetic-unit",
    difficulty="medium",
):
    """One cases[] entry in maggregate.json's real schema (the keys
    mbenchmark.aggregate writes). derive reads best_generation,
    first_pass_bloat_removed_pct, bloat_removed_pct, feedback_gain_pp,
    improved_over_baseline; the rest is carried for schema fidelity."""
    return {
        "case": case,
        "kind": kind,
        "difficulty": difficulty,
        "verdict": (
            "improved (best candidate returned)"
            if improved
            else "no improvement (baseline original returned)"
        ),
        "improved_over_baseline": improved,
        "best_weighted_cost": 0.0,
        "bloat_removed_pct": best_bloat,
        "first_pass_bloat_removed_pct": gen1,
        "feedback_gain_pp": gain,
        "generations_attempted": best_gen,
        "best_generation": best_gen,
        "first_scored_generation": 1,
        "floor_reached": True,
        "total_cost_usd": 0.05,
        "total_input_tokens": 1000,
        "total_output_tokens": 2000,
        "best_flags": [],
        "halted": None,
        "structural_changes_from_first": [],
        "per_metric": [],
        "run_dir": f"/runs/{case}",
    }


def _write_snapshot(snapshot_dir, name, cases, *, model="claude-opus-4-8", config=None):
    """Write one maggregate.json snapshot into snapshot_dir/name/maggregate.json."""
    config = config or {"cap": 5, "plateau_limit": 2}
    agg = {
        "model": model,
        "config": config,
        "n_cases": len(cases),
        "improved": sum(c["improved_over_baseline"] for c in cases),
        "baseline_returned": sum(not c["improved_over_baseline"] for c in cases),
        "cases": cases,
    }
    run_dir = Path(snapshot_dir) / name
    run_dir.mkdir(parents=True)
    (run_dir / "maggregate.json").write_text(
        json.dumps(agg, indent=2), encoding="utf-8"
    )
    return run_dir / "maggregate.json"


def _three_run_dataset(snapshot_dir):
    """Three snapshots over two cases with KNOWN inputs (a subset of the real
    mvariance shape), so the derived arrays/counts are predictable."""
    _write_snapshot(
        snapshot_dir,
        "run_00",
        [
            _case("doc_history", 1, 100.6, 100.6, 0.0),
            _case("rate_limiter", 1, 104.0, 104.0, 0.0),
        ],
    )
    _write_snapshot(
        snapshot_dir,
        "run_01",
        [
            _case("doc_history", 2, 94.4, 108.2, 13.77),
            _case("rate_limiter", 2, 93.0, 105.8, 12.79),
        ],
    )
    _write_snapshot(
        snapshot_dir,
        "run_02",
        [
            _case("doc_history", 2, 97.8, 121.8, 24.02),
            _case("rate_limiter", 3, 95.8, 101.7, 5.96),
        ],
    )


# ----------------------------------------------------------- derive: arrays + counts


def test_derive_arrays_and_counts(tmp_path):
    _three_run_dataset(tmp_path)
    ds = vh.derive(tmp_path)

    assert ds["n_runs"] == 3
    assert ds["model"] == "claude-opus-4-8"
    assert ds["config"] == {"cap": 5, "plateau_limit": 2}

    doc = ds["cases"]["doc_history"]
    assert doc["best_generation"] == [1, 2, 2]
    # gen1_bloat_removed_pct is MAPPED from each snapshot's first_pass_bloat_removed_pct.
    assert doc["gen1_bloat_removed_pct"] == [100.6, 94.4, 97.8]
    assert doc["feedback_gain_pp"] == [0.0, 13.77, 24.02]
    # best_bloat_removed_pct is MAPPED from each snapshot's bloat_removed_pct.
    assert doc["best_bloat_removed_pct"] == [100.6, 108.2, 121.8]
    assert doc["one_shot_runs"] == 1 and doc["needed_feedback_runs"] == 2

    rate = ds["cases"]["rate_limiter"]
    assert rate["best_generation"] == [1, 2, 3]
    assert rate["one_shot_runs"] == 1 and rate["needed_feedback_runs"] == 2

    # The per-case field order matches the committed mvariance structure.
    assert list(doc.keys()) == [
        "best_generation",
        "gen1_bloat_removed_pct",
        "feedback_gain_pp",
        "best_bloat_removed_pct",
        "one_shot_runs",
        "needed_feedback_runs",
    ]


def test_derive_computable_findings(tmp_path):
    _three_run_dataset(tmp_path)
    ds = vh.derive(tmp_path)

    # Every case-run improved over baseline: 6 case-runs, 0 regressions.
    assert (
        "6 improved over baseline and 0 returned baseline" in ds["stable_findings"][0]
    )
    # gen1 range across all cases/runs: min 93.0, max 104.0.
    assert "93 to 104 percent" in ds["stable_findings"][1]
    # Only run_00 had BOTH cases one-shot.
    assert ds["unstable_findings"][0].startswith("1 of 3 runs had all 2 cases one-shot")
    # feedback_gain_pp range across all cases/runs: 0 to 24.02.
    assert "ranged from 0 to 24.02 percentage points" in ds["unstable_findings"][1]


def test_derive_is_byte_identical_on_rerun(tmp_path):
    """Deterministic + order-stable: deriving twice on the same snapshots yields
    byte-identical JSON (TASK CONSTRAINT 3)."""
    _three_run_dataset(tmp_path)
    first = json.dumps(vh.derive(tmp_path), indent=2)
    second = json.dumps(vh.derive(tmp_path), indent=2)
    assert first == second


def test_derive_reads_real_mbenchmark_snapshot(tmp_path):
    """derive reads a snapshot produced by the REAL mbenchmark.aggregate +
    write_aggregate (proving the field mapping matches the actual maggregate schema
    P5.3b will emit), with no model call."""
    rows = [
        _summary_row("doc_history", 2, 94.4, 108.2, 13.77),
        _summary_row("rate_limiter", 1, 104.0, 104.0, 0.0),
        _summary_row("task_scheduler", 2, 93.5, 103.7, 10.21),
    ]
    agg = mbenchmark.aggregate(rows, "claude-opus-4-8", 5, 2)
    snap = tmp_path / "run_00"
    snap.mkdir()
    mbenchmark.write_aggregate(agg, snap)  # writes run_00/maggregate.json

    ds = vh.derive(tmp_path)
    assert ds["n_runs"] == 1
    assert ds["cases"]["doc_history"]["gen1_bloat_removed_pct"] == [94.4]
    assert ds["cases"]["doc_history"]["best_bloat_removed_pct"] == [108.2]
    assert ds["cases"]["rate_limiter"]["best_generation"] == [1]
    assert ds["cases"]["task_scheduler"]["feedback_gain_pp"] == [10.21]


def _summary_row(case, best_gen, first_pass, bloat, gain):
    """A summarize_mrun-shaped row mbenchmark.aggregate consumes (real schema)."""
    return {
        "case": case,
        "kind": "synthetic-unit",
        "difficulty": "medium",
        "verdict": "improved (best candidate returned)",
        "improved_over_baseline": True,
        "best_weighted_cost": 0.0,
        "bloat_removed_pct": bloat,
        "first_pass_bloat_removed_pct": first_pass,
        "feedback_gain_pp": gain,
        "generations_attempted": best_gen,
        "best_generation": best_gen,
        "first_scored_generation": 1,
        "floor_reached": True,
        "total_cost_usd": 0.05,
        "total_input_tokens": 1000,
        "total_output_tokens": 2000,
        "best_flags": [],
        "halted": None,
        "structural_changes_from_first": [],
        "per_metric": [],
        "run_dir": f"/runs/{case}",
    }


def test_format_mresults_rows(tmp_path):
    _three_run_dataset(tmp_path)
    ds = vh.derive(tmp_path)
    rows = vh.format_mresults_rows(ds)
    assert rows[0] == "| `doc_history` | 1, 2, 2 | 1/3 | 0 to 24.02 |"
    assert rows[1] == "| `rate_limiter` | 1, 2, 3 | 1/3 | 0 to 12.79 |"


# ----------------------------------------------------- run orchestration (stubbed)


def test_run_orchestration_with_stub_no_api(tmp_path):
    """run() loops N times, writes N distinct snapshots, and derives -- all through a
    STUBBED runner that writes a fixture instead of calling the model, so there is no
    API call and no mbenchmark execution."""
    calls = []

    def stub_runner(out_dir, *, cap, plateau, model):
        calls.append(Path(out_dir))
        return _write_snapshot(
            out_dir.parent,
            out_dir.name,
            [
                _case("doc_history", 1, 100.0, 100.0, 0.0),
                _case("rate_limiter", 2, 90.0, 105.0, 15.0),
                _case("task_scheduler", 1, 98.0, 98.0, 0.0),
            ],
            config={"cap": cap, "plateau_limit": plateau},
        )

    dataset, written = vh.run(3, tmp_path, cap=5, plateau=2, runner=stub_runner)

    assert len(calls) == 3  # invoked N times
    assert calls == [tmp_path / "run_00", tmp_path / "run_01", tmp_path / "run_02"]
    assert len({str(p) for p in written}) == 3  # N DISTINCT snapshot paths
    assert all(p.exists() and p.name == "maggregate.json" for p in written)
    assert dataset["n_runs"] == 3  # derived from the N snapshots
    assert dataset["cases"]["doc_history"]["best_generation"] == [1, 1, 1]
    assert dataset["cases"]["rate_limiter"]["needed_feedback_runs"] == 3


def test_default_runner_is_the_real_mbenchmark_seam():
    """The default runner is the real mbenchmark invocation (the seam tests replace);
    it is built but never called in P5.3a."""
    import inspect

    assert (
        inspect.signature(vh.run).parameters["runner"].default is vh._mbenchmark_runner
    )
