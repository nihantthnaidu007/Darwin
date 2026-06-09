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

Deliberately NOT built: resume-on-crash (runs are seconds-long and sub-dollar for
the whole corpus; resume solves a problem we do not have at this scale). The API
key is loaded from the environment by generator._load_dotenv() on import; it is
never read or printed here.

Usage:
  python benchmark.py                       # run the whole corpus, default loop config
  python benchmark.py --cap 5 --plateau 2   # explicit loop config (loop's own defaults)
  python benchmark.py --cases sum_evens income_tax   # a subset (cheap re-runs)
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import generator
import loop
import report
from run_summary import summarize_run

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "cases"
REPORTS = ROOT / "reports"


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
    m = json.loads((CASES / case / "meta.json").read_text(encoding="utf-8"))
    return m.get("category", "?"), m.get("difficulty", "?")


def run_benchmark(cases, cap, plateau, model):
    """Run the UNMODIFIED loop over each case and collect its per-run summary."""
    rows = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] running loop on {case} "
              f"(cap={cap}, plateau={plateau}, model={model}) ...", flush=True)
        _summary, run_dir = loop.run_loop(case, cap, plateau, model)  # loop UNMODIFIED
        s = summarize_run(run_dir)                                    # read its own logs
        category, difficulty = _case_meta(case)
        s["category"], s["difficulty"] = category, difficulty
        rows.append(s)
        print(f"      -> {s['verdict']}; best gen {s['best_generation']}; "
              f"bloat removed {s['bloat_removed_pct']}%; ${s['total_cost_usd']}",
              flush=True)
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
        "feedback_load_bearing": bool(needed_feedback),
        "total_cost_usd": round(sum(r["total_cost_usd"] for r in rows), 6),
        "total_input_tokens": sum(r["total_input_tokens"] for r in rows),
        "total_output_tokens": sum(r["total_output_tokens"] for r in rows),
        "by_category": _group(rows, "category"),
        "by_difficulty": _group(rows, "difficulty"),
        "cases": cases,
    }


def print_table(agg):
    print("\n" + "=" * 92)
    print(f"AGGREGATE  model={agg['model']}  cap={agg['config']['cap']} "
          f"plateau={agg['config']['plateau_limit']}  cases={agg['n_cases']}")
    print("=" * 92)
    print(f"  {'case':<18}{'category':<18}{'diff':<8}{'result':<16}"
          f"{'bestgen':>8}{'gens':>6}{'bloat%':>8}{'cost$':>9}")
    print("  " + "-" * 88)
    for c in agg["cases"]:
        result = "improved" if c["improved_over_baseline"] else "baseline-kept"
        print(f"  {c['case']:<18}{c['category']:<18}{c['difficulty']:<8}{result:<16}"
              f"{c['best_generation']:>8}{c['generations_attempted']:>6}"
              f"{c['bloat_removed_pct']:>8}{c['total_cost_usd']:>9}")
    print("  " + "-" * 88)
    one_shot = agg["improved"] - len(agg["needed_feedback_cases"])
    print(f"  improved {agg['improved']}/{agg['n_cases']}   "
          f"baseline-returned {agg['baseline_returned']}/{agg['n_cases']}   "
          f"one-shot {one_shot}/{agg['improved']}   "
          f"needed gen2+ {len(agg['needed_feedback_cases'])}/{agg['improved']}")
    print(f"  total cost ${agg['total_cost_usd']}  "
          f"(tokens in/out {agg['total_input_tokens']}/{agg['total_output_tokens']})")
    if agg["needed_feedback_cases"]:
        print("  feedback reached best at gen 2+ for: " + ", ".join(
            f"{c['case']}(gen{c['best_generation']}, gen1 already "
            f"{c['first_pass_bloat_removed_pct']}%, +{c['feedback_gain_pp']}pp)"
            for c in agg["needed_feedback_cases"]))
    else:
        print("  feedback NOT load-bearing: every improved case best at generation 1")
    print("=" * 92 + "\n")


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
    args = ap.parse_args()

    out = Path(args.out)
    if args.report_only:  # re-render the report from the last aggregate; runs NO loop
        agg = json.loads((out / "aggregate.json").read_text(encoding="utf-8"))
        generated_at = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
        (out / "RESULTS.md").write_text(report.build_markdown(agg, generated_at),
                                        encoding="utf-8")
        print_table(agg)
        print(f"re-rendered {out / 'RESULTS.md'} from {out / 'aggregate.json'} (no API calls)")
        return

    cases = args.cases or discover_cases()
    if not cases:
        raise SystemExit(f"no complete cases found under {CASES}")
    print(f"corpus: {len(cases)} case(s) -> {', '.join(cases)}\n")

    rows = run_benchmark(cases, args.cap, args.plateau, args.model)
    agg = aggregate(rows, args.model, args.cap, args.plateau)
    print_table(agg)

    out.mkdir(parents=True, exist_ok=True)
    generated_at = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
    (out / "aggregate.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")
    (out / "RESULTS.md").write_text(report.build_markdown(agg, generated_at),
                                    encoding="utf-8")
    print(f"wrote {out / 'aggregate.json'}")
    print(f"wrote {out / 'RESULTS.md'}")


if __name__ == "__main__":
    main()
