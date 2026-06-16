"""Phase V3 — multi-file per-run summary: a clean, readable view of ONE mloop run.
The multi-file analogue of tools/run_summary.py.

This is a PURE REPORTING LAYER over the loop's existing logs. It re-instruments
nothing: it reads the run's own run.json (already written by mloop.py, with real
token counts, cost, and a full per-generation trace) plus the case's
baseline_metrics.json, and re-presents them. The only things it *derives* are the
honesty-relevant facts the loop already implies:

  - which generation actually produced the returned best candidate (the key
    "was the feedback loop load-bearing on multi-file?" signal);
  - what generation 1 alone achieved versus how many extra percentage points the
    later generations added on top of it (the magnitude test — a case where gen 1
    already removed almost everything and feedback added a fraction of a point is
    NOT feedback doing real work; see decision 0006, the single-function finding);
  - exactly which aggregate metrics feedback moved between the first scored
    generation and the returned best;
  - whether the reference floor was reached (weighted_cost <= 0.0);
  - the per-metric reduction original -> best, anchored to the reference floor.

Two multi-file specifics versus run_summary:
  - the baseline shape is original = baseline["original"]["aggregate"] and
    floor = baseline["reference"]["aggregate"] (the key is "reference", not
    "reference_floor"), since the multi-file basket is aggregated across files;
  - each trace record's metrics is the FULL basket {aggregate, per_file} that
    mloop stores, so the score reads off rec["metrics"]["aggregate"].

Method A (the weighted cost / per-metric normalization) is NOT re-implemented here:
evaluator.WEIGHTS and mevaluator._metric_costs (the multi-file per-metric cost basis)
are imported so the score lives in exactly one place. The weighted cost itself is
read straight from the loop's own log, never recomputed. Importing this module does
not touch the API or Docker.

Usage: python mrun_summary.py <run_dir>     # pretty-print one mloop run's summary
"""
import sys
from pathlib import Path

import runinput
from evaluator import WEIGHTS
from mevaluator import _metric_costs

ROOT = Path(__file__).resolve().parent.parent
MCASES = ROOT / "mcases"

# Structural metrics that actually drive Method A (weight > 0), in display order.
# maintainability_index is weight 0 (cosmetic-gameable; see evaluator.py) AND lives
# per-file only in the multi-file basket, so it is never in the aggregate; source_loc
# is also weight 0. Both are excluded from the scored view here, as in run_summary.
STRUCTURAL = [m for m, w in WEIGHTS.items() if w > 0]
_LABEL = {
    "cyclomatic_total": "cyclomatic_total", "logical_loc": "logical_loc",
    "max_nesting_depth": "max_nesting_depth", "dependency_count": "dependency_count",
    "dead_code_count": "dead_code_count", "cyclomatic_max": "cyclomatic_max",
}


def _best_record(trace):
    """The trace record for the candidate the loop actually returned. mloop marks
    every strict improvement with is_improvement, so the LAST is_improvement record
    is the returned best; if nothing improved on the baseline, the baseline (gen 0)
    is it. Same contract as run_summary._best_record."""
    improving = [r for r in trace if r.get("is_improvement")]
    return improving[-1] if improving else trace[0]


def _aggregate_of(rec, fallback):
    """The aggregate metric basket from a trace record. mloop stores the full
    {aggregate, per_file} basket on every baseline/scored record; a record with no
    metrics (a rejected/invalid generation) falls back to `fallback`."""
    basket = rec.get("metrics")
    return basket["aggregate"] if basket else fallback


def summarize_mrun(run_dir):
    """Read run.json + baseline_metrics.json for a finished mloop run and return a
    clean summary dict (no new measurement — only re-presentation + a few
    derivations the loop already implies)."""
    run_dir = Path(run_dir)
    run = runinput.load_json(run_dir / "run.json")
    baseline = runinput.load_json(MCASES / run["case"] / "baseline_metrics.json")
    # Multi-file baseline shape: the aggregate of the basket, key "reference" (not
    # "reference_floor"), since the basket is aggregated across the unit's files.
    original = baseline["original"]["aggregate"]
    floor = baseline["reference"]["aggregate"]

    trace = run["trace"]
    best_rec = _best_record(trace)
    best_gen = best_rec["generation"]
    best_agg = _aggregate_of(best_rec, original)  # gen 0 (baseline) carries metrics too

    # First-pass result: the FIRST scored generation. Comparing it to the returned
    # best is the honest magnitude test for "was feedback load-bearing?" — if the
    # best came from a later generation, how much did that later feedback actually
    # add on top of what generation 1 already achieved?
    scored = [r for r in trace if r.get("verdict") == "scored"]
    first = scored[0] if scored else None

    # Per-metric reduction, anchored to the case's own original->floor scale via the
    # SAME multi-file per-metric cost mevaluator uses (0.0 = at the floor, 1.0 = as
    # bloated as the original); we do not invent a new scale or re-derive the cost.
    best_costs = _metric_costs(best_agg, original, floor)
    per_metric = []
    for m in STRUCTURAL:
        c = best_costs.get(m)
        per_metric.append({
            "metric": m,
            "original": original[m],
            "best": best_agg[m],
            "floor": floor[m],
            "norm_cost": c,                         # None where this case gives no signal
            "at_or_below_floor": (c is not None and c <= 0.0),
        })

    # Weighted costs come straight from the loop's own log — never recomputed here.
    best_wc = run["best_weighted_cost"]
    first_wc = first["weighted_cost"] if first else None
    first_agg = _aggregate_of(first, {}) if first else {}
    first_bloat = round((1.0 - first_wc) * 100, 1) if first_wc is not None else None

    # Magnitude of any later-generation gain over the first pass (honest "load-bearing"
    # test). structural_changes_from_first names exactly which structural metrics the
    # feedback moved between the first scored gen and the returned best.
    # Feedback attribution only makes sense when the returned best actually came from a
    # scored generation (best_generation >= 1). If the baseline was kept (best_gen == 0),
    # feedback moved nothing -- even if some scored-but-worse generations exist -- so do
    # NOT report a gain or a structural delta against the baseline; that would mislead-
    # ingly credit feedback for the baseline's own metrics.
    if best_gen >= 1 and first_wc is not None and best_wc is not None:
        feedback_gain_pp = round((first_wc - best_wc) * 100, 2)
        structural_changes = [
            {"metric": m, "first_pass": first_agg[m], "best": best_agg[m]}
            for m in STRUCTURAL if best_agg.get(m) != first_agg.get(m)]
    else:
        feedback_gain_pp, structural_changes = None, []

    return {
        "case": run["case"],
        "model": run["model"],
        "config": run["config"],
        "verdict": ("improved (best candidate returned)" if run["improved_over_baseline"]
                    else "no improvement (baseline original returned)"),
        "improved_over_baseline": run["improved_over_baseline"],
        "returned": run["returned"],
        "halted": run["halted"],
        # Honesty fields:
        "generations_attempted": run["generations"],   # how many gens the loop ran
        "best_generation": best_gen,                    # which gen produced the kept best
        "first_scored_generation": (first["generation"] if first else None),
        "first_pass_weighted_cost": first_wc,
        "first_pass_bloat_removed_pct": first_bloat,    # what gen 1 alone achieved
        "feedback_gain_pp": feedback_gain_pp,           # extra pp the later gens added
        "structural_changes_from_first": structural_changes,  # what feedback actually moved
        "floor_reached": (best_wc is not None and best_wc <= 0.0),
        # Scores on the case's own original->floor scale (1.0 = original, 0.0 = floor):
        "baseline_weighted_cost": run["baseline_weighted_cost"],
        "best_weighted_cost": best_wc,
        # "bloat removed" = fraction of the original->floor span closed, in %. >100%
        # (below_floor) means the candidate scored BELOW the clean reference floor --
        # the engine flags these (suspiciously-simple), it does not reward them.
        "bloat_removed_pct": (round((1.0 - best_wc) * 100, 1)
                              if best_wc is not None else None),
        "below_floor": (best_wc is not None and best_wc < 0.0),
        "per_metric": per_metric,
        "best_flags": best_rec.get("flags", []),
        "original_metrics": original,
        "best_metrics": best_agg,
        "reference_floor": floor,
        # Cost/observability — read straight from the loop's own log, not recomputed.
        "total_input_tokens": run["total_input_tokens"],
        "total_output_tokens": run["total_output_tokens"],
        "total_cost_usd": run["total_cost_usd"],
        "run_dir": str(run_dir),
    }


def print_summary(s):
    print("=" * 78)
    print(f"MRUN SUMMARY  {s['case']}   (model={s['model']}, "
          f"cap={s['config']['cap']}, plateau={s['config']['plateau_limit']})")
    print("=" * 78)
    print(f"  verdict           : {s['verdict']}")
    print(f"  weighted cost     : baseline 1.0  ->  best {s['best_weighted_cost']}   "
          f"(0.0 = clean floor; lower is better)")
    floor_note = ("   [scored BELOW the clean floor -> flagged, not rewarded]"
                  if s["below_floor"] else "")
    print(f"  bloat removed     : {s['bloat_removed_pct']}%   (of this case's own "
          f"original->floor span){floor_note}")
    print(f"  floor reached     : {s['floor_reached']}")
    print(f"  generations run   : {s['generations_attempted']}    "
          f"best candidate from generation {s['best_generation']}"
          + ("   <- one-shot (gen 1)" if s['best_generation'] == 1 else
             "   <- baseline kept" if s['best_generation'] == 0 else
             f"   <- needed feedback (gen {s['best_generation']})"))
    if s["best_generation"] >= 2:
        changes = ", ".join(f"{c['metric']} {c['first_pass']}->{c['best']}"
                            for c in s["structural_changes_from_first"]) or "none (noise only)"
        print(f"  feedback magnitude: gen 1 alone removed {s['first_pass_bloat_removed_pct']}%; "
              f"later gens added {s['feedback_gain_pp']} pp  (structural change: {changes})")
    if s["best_flags"]:
        print(f"  guard flags       : {', '.join(s['best_flags'])}")
    if s["halted"]:
        print(f"  HALTED            : {s['halted']}")
    print(f"  cost              : ${s['total_cost_usd']}   "
          f"(tokens in/out {s['total_input_tokens']}/{s['total_output_tokens']})")

    print(f"\n  {'metric':<20}{'original':>10}{'best':>8}{'floor':>8}{'to floor':>9}"
          f"{'norm cost':>11}  (0=floor,1=orig)")
    print("  " + "-" * 73)
    for pm in s["per_metric"]:
        nc = "n/a" if pm["norm_cost"] is None else f"{pm['norm_cost']:.3f}"
        mark = "  *at/below floor" if pm["at_or_below_floor"] else ""
        print(f"  {_LABEL[pm['metric']]:<20}{pm['original']:>10}{pm['best']:>8}"
              f"{pm['floor']:>8}{pm['best'] - pm['floor']:>9}{nc:>11}{mark}")
    print(f"  (maintainability_index informational only — per-file, weight 0; not scored)")
    print(f"\n  artifacts: {s['run_dir']}\n")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python mrun_summary.py <run_dir>")
    print_summary(summarize_mrun(sys.argv[1]))


if __name__ == "__main__":
    main()
