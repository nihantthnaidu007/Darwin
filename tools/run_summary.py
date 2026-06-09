"""Phase 4 — per-run summary: a clean, readable view of ONE case run.

This is a PURE REPORTING LAYER over the loop's existing logs. It re-instruments
nothing: it reads the run's own run.json (already written by loop.py, with real
token counts, cost, and a full per-generation trace) plus the case's
baseline_metrics.json (original + reference_floor), and re-presents them. The only
things it *derives* are honesty-relevant facts the loop already implies:

  - which generation actually produced the returned best candidate (the key
    "was the feedback loop load-bearing?" signal);
  - whether the reference floor was reached (weighted_cost <= 0.0);
  - the per-metric reduction original -> best, anchored to the reference floor.

Method A (the weighted cost / per-metric normalization) is NOT re-implemented here:
evaluator.WEIGHTS and evaluator.metric_costs are imported so the score lives in
exactly one place. Importing this module does not touch the API.

Usage: python run_summary.py <run_dir>     # pretty-print one run's summary
"""
import json
import sys
from pathlib import Path

from evaluator import WEIGHTS, metric_costs

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "cases"

# Structural metrics that actually drive Method A (weight > 0), in display order.
# maintainability_index is shown separately as informational (weight 0 — it is
# cosmetic-gameable at single-function scale; see evaluator.py).
STRUCTURAL = [m for m, w in WEIGHTS.items() if w > 0]
_LABEL = {
    "cyclomatic_total": "cyclomatic_total", "logical_loc": "logical_loc",
    "max_nesting_depth": "max_nesting_depth", "dependency_count": "dependency_count",
    "dead_code_count": "dead_code_count", "cyclomatic_max": "cyclomatic_max",
}


def _best_record(trace):
    """The trace record for the candidate the loop actually returned. The loop sets
    `best` on every strict improvement, so the LAST is_improvement record is the
    returned best; if nothing improved on the baseline, the baseline (gen 0) is it."""
    improving = [r for r in trace if r.get("is_improvement")]
    return improving[-1] if improving else trace[0]


def summarize_run(run_dir):
    """Read run.json + baseline_metrics.json for a finished run and return a clean
    summary dict (no new measurement — only re-presentation + a few derivations)."""
    run_dir = Path(run_dir)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    baseline = json.loads(
        (CASES / run["case"] / "baseline_metrics.json").read_text(encoding="utf-8"))
    original, floor = baseline["original"], baseline["reference_floor"]

    trace = run["trace"]
    best_rec = _best_record(trace)
    best_gen = best_rec["generation"]
    best_metrics = best_rec.get("metrics") or original  # gen 0 (baseline) has metrics too

    # First-pass result: the FIRST scored generation. Comparing it to the returned
    # best is the honest magnitude test for "was feedback load-bearing?" — if the best
    # came from a later generation, how much did that later feedback actually add on
    # top of what generation 1 already achieved?
    scored = [r for r in trace if r.get("verdict") == "scored"]
    first = scored[0] if scored else None

    # Per-metric reduction, anchored to the case's own original->floor scale. The
    # normalized cost is the evaluator's own number (0.0 = at the floor, 1.0 = as
    # bloated as the original); we do not invent a new scale.
    best_costs = metric_costs(best_metrics, baseline)
    orig_costs = metric_costs(original, baseline)
    per_metric = []
    for m in STRUCTURAL:
        c = best_costs[m]
        per_metric.append({
            "metric": m,
            "original": original[m],
            "best": best_metrics[m],
            "floor": floor[m],
            "norm_cost": c,                         # None where this case gives no signal
            "at_or_below_floor": (c is not None and c <= 0.0),
        })

    best_wc = run["best_weighted_cost"]

    # Magnitude of any later-generation gain over the first pass (honest "load-bearing"
    # test). structural_changes_from_first names exactly which structural metrics the
    # feedback moved between the first scored gen and the returned best.
    first_wc = first["weighted_cost"] if first else None
    first_metrics = (first.get("metrics") or {}) if first else {}
    first_bloat = round((1.0 - first_wc) * 100, 1) if first_wc is not None else None
    # Feedback attribution only makes sense when the returned best actually came from a
    # scored generation (best_generation >= 1). If the baseline was kept (best_gen == 0),
    # feedback moved nothing -- even if some scored-but-worse generations exist -- so do
    # NOT report a gain or a structural delta against the baseline; that would misleadingly
    # credit feedback for the baseline's own metrics.
    if best_gen >= 1 and first_wc is not None and best_wc is not None:
        feedback_gain_pp = round((first_wc - best_wc) * 100, 2)
        structural_changes = [
            {"metric": m, "first_pass": first_metrics[m], "best": best_metrics[m]}
            for m in STRUCTURAL if best_metrics.get(m) != first_metrics.get(m)]
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
        "best_metrics": best_metrics,
        "reference_floor": floor,
        # Cost/observability — read straight from the loop's own log, not recomputed.
        "total_input_tokens": run["total_input_tokens"],
        "total_output_tokens": run["total_output_tokens"],
        "total_cost_usd": run["total_cost_usd"],
        "run_dir": str(run_dir),
    }


def _fmt_signal(v):
    return f"{v:+.3f}" if isinstance(v, (int, float)) else "  n/a"


def print_summary(s):
    print("=" * 78)
    print(f"RUN SUMMARY  {s['case']}   (model={s['model']}, "
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
    print(f"  (maintainability_index informational only — weight 0; not scored)")
    print(f"\n  artifacts: {s['run_dir']}\n")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python run_summary.py <run_dir>")
    print_summary(summarize_run(sys.argv[1]))


if __name__ == "__main__":
    main()
