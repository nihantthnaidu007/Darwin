"""Phase 4/5 — the validation harness: one command runs the EXISTING loop over
EVERY case and aggregates the EXISTING per-run logs into summaries + an honest
report. It is thin orchestration plus reporting; it adds no engine, evaluator,
sandbox, metric, or case logic.

  - It calls loop.run_loop() UNMODIFIED, in-process, once per case (the loop writes
    its own run.json / gen_NN.json exactly as in Phase 3).
  - It reuses run_summary.summarize_run() to read each run's logs back (cost and
    per-generation data are NOT recomputed — they come from the loop's own logs).
  - It aggregates across cases, writes reports/aggregate.json (machine) and
    reports/RESULTS.md (the honest report, headline derived from the data), and
    prints a clean table.

Checkpointing (P4.2): each case result is persisted to runs/ the moment it
completes (via the shared runstate helper), so a crash never discards finished
work. A fresh run clears prior state and rewrites it; --resume skips cases already
recorded and runs only the rest, assembling the same final aggregate. The API key
is loaded from the environment by generator._load_dotenv(); it is never read or
printed here.

Usage:
  python benchmark.py                       # fresh run of the whole corpus (clears prior state)
  python benchmark.py --resume              # resume an interrupted run; skip completed cases
  python benchmark.py --cap 5 --plateau 2   # explicit loop config (loop's own defaults)
  python benchmark.py --cases sum_evens income_tax   # a subset (cheap re-runs)
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import generator
import logsetup
import loop
import report
import runinput
import runstate
from feedback_materiality import FEEDBACK_MATERIALITY_EPSILON_PP
from run_summary import summarize_run

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "cases"
REPORTS = ROOT / "reports"
RUNS = ROOT / "runs"

log = logsetup.get_logger("benchmark")  # operational log -> stderr (configured at the entry point)
# Per-case checkpoint of completed cases (under the gitignored runs/). A fresh run
# clears this and rewrites it; --resume reads it to skip already-completed cases.
RUN_STATE = RUNS / "benchmark_runstate.jsonl"


def discover_cases():
    """Every directory under cases/ that is a complete case (the loop needs all of
    these). Sorted for deterministic ordering."""
    found = []
    for d in sorted(CASES.iterdir()):
        if all((d / f).exists() for f in
               ("meta.json", "original.py", "baseline_metrics.json",
                "test_suite.py", "golden_io.json")):
            found.append(d.name)
    return found


def _case_meta(case):
    m = runinput.load_case_meta(CASES / case)
    return m.get("category", "?"), m.get("difficulty", "?")


def run_benchmark(cases, cap, plateau, model, run_loop=loop.run_loop,
                  state=None, resume=False):
    """Run the UNMODIFIED loop over each case and collect its per-run summary.

    `run_loop` is an injectable seam (default loop.run_loop) so the orchestration
    is testable with a fake loop -- no API key and no Docker. Checkpointing is
    additive: with a `state` (a runstate.RunState), a fresh run clears prior state
    and persists each case as it completes; with resume=True, cases already in the
    state are skipped and their persisted summaries reused, so the assembled rows
    -- and therefore the aggregate -- are the union of resumed and newly run cases,
    identical to a complete fresh run.
    """
    if state is not None:
        config = runstate.run_config(model, cap, plateau)
        if resume:
            done = state.resume(config)          # fail closed if the config mismatches
        else:
            state.start(config)                  # fresh run: record config, clear prior
            done = {}
    else:
        done = {}
    rows = []
    for i, case in enumerate(cases, 1):
        if case in done:                                 # resumed: reuse persisted result
            log.info("[%s/%s] %s already complete -> skipped (resumed)",
                     i, len(cases), case, extra={"case": case, "resumed": True})
            rows.append(done[case])
            continue
        log.info("[%s/%s] running loop on %s (cap=%s, plateau=%s, model=%s) ...",
                 i, len(cases), case, cap, plateau, model)
        _summary, run_dir = run_loop(case, cap, plateau, model)  # loop UNMODIFIED
        s = summarize_run(run_dir)                                # read its own logs
        category, difficulty = _case_meta(case)
        s["category"], s["difficulty"] = category, difficulty
        if state is not None:
            state.append(case, s)                        # persist the moment it completes
        rows.append(s)
        log.info("      -> %s; best gen %s; bloat removed %s%%; $%s",
                 s["verdict"], s["best_generation"], s["bloat_removed_pct"],
                 s["total_cost_usd"],
                 extra={"case": case, "model": model, "verdict": s["verdict"],
                        "improved_over_baseline": s["improved_over_baseline"],
                        "best_generation": s["best_generation"],
                        "bloat_removed_pct": s["bloat_removed_pct"],
                        "total_cost_usd": s["total_cost_usd"],
                        "total_input_tokens": s["total_input_tokens"],
                        "total_output_tokens": s["total_output_tokens"]})
    return rows


def _group(rows, key):
    out = {}
    for r in rows:
        g = out.setdefault(r[key], {"n": 0, "improved": 0, "one_shot": 0, "_bloat": []})
        g["n"] += 1
        g["improved"] += int(r["improved_over_baseline"])
        g["one_shot"] += int(r["improved_over_baseline"] and r["best_generation"] == 1)
        g["_bloat"].append(r["bloat_removed_pct"] or 0.0)
    for g in out.values():
        g["avg_bloat_removed_pct"] = round(sum(g["_bloat"]) / len(g["_bloat"]), 1)
        del g["_bloat"]
    return out


def aggregate(rows, model, cap, plateau):
    improved = [r for r in rows if r["improved_over_baseline"]]
    # The honesty pivot: among improved cases, which needed generation 2+ to reach
    # their best -- AND by how much (magnitude, not just direction). A case where
    # generation 1 already removed 99% and feedback added a fraction of a point is NOT
    # the same as feedback doing real work; the report must not conflate them.
    needed_feedback = [{
        "case": r["case"], "best_generation": r["best_generation"],
        "first_scored_generation": r["first_scored_generation"],
        "first_pass_bloat_removed_pct": r["first_pass_bloat_removed_pct"],
        "best_bloat_removed_pct": r["bloat_removed_pct"],
        "feedback_gain_pp": r["feedback_gain_pp"],
        "structural_changes_from_first": r["structural_changes_from_first"],
    } for r in improved if r["best_generation"] >= 2]
    cases = [{
        "case": r["case"], "category": r["category"], "difficulty": r["difficulty"],
        "verdict": r["verdict"], "improved_over_baseline": r["improved_over_baseline"],
        "best_weighted_cost": r["best_weighted_cost"],
        "bloat_removed_pct": r["bloat_removed_pct"],
        "first_pass_bloat_removed_pct": r["first_pass_bloat_removed_pct"],
        "feedback_gain_pp": r["feedback_gain_pp"],
        "generations_attempted": r["generations_attempted"],
        "best_generation": r["best_generation"],
        "first_scored_generation": r["first_scored_generation"],
        "floor_reached": r["floor_reached"],
        "total_cost_usd": r["total_cost_usd"],
        "total_input_tokens": r["total_input_tokens"],
        "total_output_tokens": r["total_output_tokens"],
        "best_flags": r["best_flags"], "halted": r["halted"],
        "structural_changes_from_first": r["structural_changes_from_first"],
        "per_metric": r["per_metric"], "run_dir": r["run_dir"],
    } for r in rows]
    return {
        "model": model, "config": {"cap": cap, "plateau_limit": plateau},
        "n_cases": len(rows),
        "improved": len(improved),
        "baseline_returned": len(rows) - len(improved),
        "needed_feedback_cases": needed_feedback,
        # Load-bearing only if some later-generation gain CLEARS the materiality floor
        # (decision 0021); direction alone (bool(needed_feedback)) credits gains within
        # run-to-run noise, so it overpromises relative to the field's name.
        "feedback_load_bearing": any(
            c["feedback_gain_pp"] > FEEDBACK_MATERIALITY_EPSILON_PP for c in needed_feedback),
        "total_cost_usd": round(sum(r["total_cost_usd"] for r in rows), 6),
        "total_input_tokens": sum(r["total_input_tokens"] for r in rows),
        "total_output_tokens": sum(r["total_output_tokens"] for r in rows),
        "by_category": _group(rows, "category"),
        "by_difficulty": _group(rows, "difficulty"),
        "cases": cases,
    }


def write_aggregate(agg, out_dir):
    """Write the machine-readable reports/aggregate.json. Returns the path. A pure
    extraction of main()'s former inline write (mirrors mbenchmark.write_aggregate),
    so the artifact byte-identity guarantee is test-enforced, not only reviewed."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "aggregate.json"
    path.write_text(json.dumps(agg, indent=2), encoding="utf-8")
    return path


def print_table(agg):
    # Pre-built aligned lines are passed as a single "%s" arg so the column layout
    # and any literal "%" survive untouched; the message-only console handler then
    # renders the table exactly as the old print did (on stderr now).
    log.info("%s", "\n" + "=" * 92)
    log.info("AGGREGATE  model=%s  cap=%s plateau=%s  cases=%s",
             agg["model"], agg["config"]["cap"], agg["config"]["plateau_limit"],
             agg["n_cases"],
             extra={"model": agg["model"], "cap": agg["config"]["cap"],
                    "plateau_limit": agg["config"]["plateau_limit"],
                    "n_cases": agg["n_cases"]})
    log.info("=" * 92)
    log.info("%s", f"  {'case':<18}{'category':<18}{'diff':<8}{'result':<16}"
                   f"{'bestgen':>8}{'gens':>6}{'bloat%':>8}{'cost$':>9}")
    log.info("%s", "  " + "-" * 88)
    for c in agg["cases"]:
        result = "improved" if c["improved_over_baseline"] else "baseline-kept"
        log.info("%s", f"  {c['case']:<18}{c['category']:<18}{c['difficulty']:<8}{result:<16}"
                       f"{c['best_generation']:>8}{c['generations_attempted']:>6}"
                       f"{c['bloat_removed_pct']:>8}{c['total_cost_usd']:>9}")
    log.info("%s", "  " + "-" * 88)
    one_shot = agg["improved"] - len(agg["needed_feedback_cases"])
    log.info("%s", f"  improved {agg['improved']}/{agg['n_cases']}   "
                   f"baseline-returned {agg['baseline_returned']}/{agg['n_cases']}   "
                   f"one-shot {one_shot}/{agg['improved']}   "
                   f"needed gen2+ {len(agg['needed_feedback_cases'])}/{agg['improved']}")
    log.info("  total cost $%s  (tokens in/out %s/%s)",
             agg["total_cost_usd"], agg["total_input_tokens"], agg["total_output_tokens"],
             extra={"total_cost_usd": agg["total_cost_usd"],
                    "total_input_tokens": agg["total_input_tokens"],
                    "total_output_tokens": agg["total_output_tokens"],
                    "improved": agg["improved"], "n_cases": agg["n_cases"]})
    if agg["needed_feedback_cases"]:
        log.info("%s", "  feedback reached best at gen 2+ for: " + ", ".join(
            f"{c['case']}(gen{c['best_generation']}, gen1 already "
            f"{c['first_pass_bloat_removed_pct']}%, +{c['feedback_gain_pp']}pp)"
            for c in agg["needed_feedback_cases"]))
    else:
        log.info("  feedback NOT load-bearing: every improved case best at generation 1")
    log.info("%s", "=" * 92 + "\n")


def main():
    ap = argparse.ArgumentParser(description="Validation harness over the whole case store")
    ap.add_argument("--cap", type=int, default=5, help="hard generation cap (loop default)")
    ap.add_argument("--plateau", type=int, default=2,
                    help="stop after this many non-improving generations (loop default)")
    ap.add_argument("--model", default=generator.DEFAULT_MODEL)
    ap.add_argument("--cases", nargs="*", default=None,
                    help="subset of case names (default: every case in cases/)")
    ap.add_argument("--out", default=str(REPORTS), help="output directory for report files")
    ap.add_argument("--report-only", action="store_true",
                    help="regenerate RESULTS.md from an existing aggregate.json (no API calls)")
    ap.add_argument("--resume", action="store_true",
                    help="resume an interrupted run: skip cases already recorded in run-state "
                         "and run only the rest (same corpus and config). Default is a fresh "
                         "run that clears prior state first.")
    args = ap.parse_args()
    logsetup.configure()   # entry point: wire logging once (never at import)

    out = Path(args.out)
    if args.report_only:  # re-render the report from the last aggregate; runs NO loop
        agg = runinput.load_json(out / "aggregate.json", "aggregate.json")
        generated_at = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
        (out / "RESULTS.md").write_text(report.build_markdown(agg, generated_at),
                                        encoding="utf-8")
        print_table(agg)
        log.info("re-rendered %s from %s (no API calls)",
                 out / "RESULTS.md", out / "aggregate.json")
        return

    cases = args.cases or discover_cases()
    if not cases:
        raise SystemExit(f"no complete cases found under {CASES}")
    log.info("corpus: %s case(s) -> %s%s",
             len(cases), ", ".join(cases), "  [resume]" if args.resume else "")

    state = runstate.RunState(RUN_STATE)
    try:
        rows = run_benchmark(cases, args.cap, args.plateau, args.model,
                             state=state, resume=args.resume)
    except runstate.ConfigMismatchError as e:
        raise SystemExit(str(e))                 # fail closed with a clear message
    agg = aggregate(rows, args.model, args.cap, args.plateau)
    print_table(agg)

    generated_at = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
    agg_path = write_aggregate(agg, out)   # aggregate.json (byte-identical; mkdirs out)
    (out / "RESULTS.md").write_text(report.build_markdown(agg, generated_at),
                                    encoding="utf-8")
    log.info("wrote %s", agg_path)
    log.info("wrote %s", out / "RESULTS.md")


if __name__ == "__main__":
    main()
