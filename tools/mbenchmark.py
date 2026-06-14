"""Phase V3 — the multi-file validation harness: one command runs the EXISTING
mloop over EVERY mcase and aggregates the EXISTING per-run logs into summaries +
a machine-readable aggregate. The multi-file analogue of tools/benchmark.py. It is
thin orchestration plus aggregation; it adds no engine, evaluator, sandbox, metric,
or case logic, and it re-scores nothing.

  - It calls mloop.run_loop() UNMODIFIED, in-process, once per mcase (the loop
    writes its own run.json / gen_NN.json exactly as in V2). The per-case call is
    injectable (run_loop=) so the orchestration and the maggregate.json writing are
    testable with a fake run_loop -- no API key and no Docker.
  - It reuses mrun_summary.summarize_mrun() to read each run's logs back (cost and
    per-generation data are NOT recomputed -- they come from the loop's own logs).
  - It aggregates across cases, writes reports/maggregate.json (machine-readable),
    and prints a clean per-case table.

The narrative report (reports/MRESULTS.md) and the multi-file one-shot decision
record are deliberately NOT built here: they are V3-P2, written against the real
numbers after the paid run. This module produces only the machine-readable
aggregate and the printed table. The API key is loaded from the environment by
generator._load_dotenv() on import of mloop's chain; it is never read or printed
here.

Usage:
  python mbenchmark.py                          # run every mcase, default loop config
  python mbenchmark.py --cap 5 --plateau 2      # explicit loop config (loop's own defaults)
  python mbenchmark.py --cases rate_limiter     # a subset (cheap re-runs)
"""
import argparse
import json
from pathlib import Path

import mgenerator
import mloop
from mrun_summary import summarize_mrun

ROOT = Path(__file__).resolve().parent.parent
MCASES = ROOT / "mcases"
REPORTS = ROOT / "reports"

# A complete mcase carries all of these (the loop needs them). original/ and
# reference/ are directories (the multi-file units); the rest are files.
_REQUIRED_FILES = ("meta.json", "corpus.py", "test_suite.py", "baseline_metrics.json")
_REQUIRED_DIRS = ("original", "reference")


def discover_mcases():
    """Every directory under mcases/ that is a complete mcase. Sorted for
    deterministic ordering."""
    found = []
    for d in sorted(MCASES.iterdir()):
        if not d.is_dir():
            continue
        if all((d / f).is_file() for f in _REQUIRED_FILES) \
                and all((d / sub).is_dir() for sub in _REQUIRED_DIRS):
            found.append(d.name)
    return found


def _case_meta(case):
    """The mcase's grouping axes. mcase meta uses 'kind' (the domain descriptor,
    the multi-file analogue of single-function 'category') and 'difficulty'."""
    m = json.loads((MCASES / case / "meta.json").read_text(encoding="utf-8"))
    return m.get("kind", "?"), m.get("difficulty", "?")


def run_benchmark(cases, cap, plateau, model, run_loop=mloop.run_loop):
    """Run the UNMODIFIED mloop over each mcase and collect its per-run summary.
    `run_loop` is an injectable seam (default mloop.run_loop) so the orchestration
    is testable with a fake loop -- no API key and no Docker."""
    rows = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] running mloop on {case} "
              f"(cap={cap}, plateau={plateau}, model={model}) ...", flush=True)
        _summary, run_dir = run_loop(case, cap, plateau, model)   # loop UNMODIFIED
        s = summarize_mrun(run_dir)                               # read its own logs
        kind, difficulty = _case_meta(case)
        s["kind"], s["difficulty"] = kind, difficulty
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
    one_shot = [r for r in improved if r["best_generation"] == 1]
    # The honesty pivot: among improved cases, which needed generation 2+ to reach
    # their best -- AND by how much (magnitude, not just direction). A case where
    # generation 1 already removed almost everything and feedback added a fraction of
    # a point is NOT the same as feedback doing real work; the report must not conflate
    # them, so each needed-feedback case carries its first-pass result and the extra pp.
    needed_feedback = [{
        "case": r["case"], "best_generation": r["best_generation"],
        "first_scored_generation": r["first_scored_generation"],
        "first_pass_bloat_removed_pct": r["first_pass_bloat_removed_pct"],
        "best_bloat_removed_pct": r["bloat_removed_pct"],
        "feedback_gain_pp": r["feedback_gain_pp"],
        "structural_changes_from_first": r["structural_changes_from_first"],
    } for r in improved if r["best_generation"] >= 2]
    cases = [{
        "case": r["case"], "kind": r["kind"], "difficulty": r["difficulty"],
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
        "one_shot": len(one_shot),
        "needed_feedback": len(needed_feedback),
        "needed_feedback_cases": needed_feedback,
        "feedback_load_bearing": bool(needed_feedback),
        "total_cost_usd": round(sum(r["total_cost_usd"] for r in rows), 6),
        "total_input_tokens": sum(r["total_input_tokens"] for r in rows),
        "total_output_tokens": sum(r["total_output_tokens"] for r in rows),
        "by_kind": _group(rows, "kind"),
        "by_difficulty": _group(rows, "difficulty"),
        "cases": cases,
    }


def write_aggregate(agg, out_dir):
    """Write the machine-readable reports/maggregate.json. Returns the path. Kept a
    separate function so the writing is testable with a fake run_loop, no API/Docker."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "maggregate.json"
    path.write_text(json.dumps(agg, indent=2), encoding="utf-8")
    return path


def print_table(agg):
    print("\n" + "=" * 100)
    print(f"MAGGREGATE  model={agg['model']}  cap={agg['config']['cap']} "
          f"plateau={agg['config']['plateau_limit']}  cases={agg['n_cases']}")
    print("=" * 100)
    print(f"  {'case':<16}{'kind':<30}{'diff':<8}{'result':<16}"
          f"{'bestgen':>8}{'gens':>6}{'bloat%':>8}{'cost$':>9}")
    print("  " + "-" * 96)
    for c in agg["cases"]:
        result = "improved" if c["improved_over_baseline"] else "baseline-kept"
        print(f"  {c['case']:<16}{c['kind'][:28]:<30}{c['difficulty']:<8}{result:<16}"
              f"{c['best_generation']:>8}{c['generations_attempted']:>6}"
              f"{c['bloat_removed_pct']:>8}{c['total_cost_usd']:>9}")
    print("  " + "-" * 96)
    print(f"  improved {agg['improved']}/{agg['n_cases']}   "
          f"baseline-returned {agg['baseline_returned']}/{agg['n_cases']}   "
          f"one-shot {agg['one_shot']}/{agg['improved']}   "
          f"needed gen2+ {agg['needed_feedback']}/{agg['improved']}")
    print(f"  total cost ${agg['total_cost_usd']}  "
          f"(tokens in/out {agg['total_input_tokens']}/{agg['total_output_tokens']})")
    if agg["needed_feedback_cases"]:
        print("  feedback reached best at gen 2+ for: " + ", ".join(
            f"{c['case']}(gen{c['best_generation']}, gen1 already "
            f"{c['first_pass_bloat_removed_pct']}%, +{c['feedback_gain_pp']}pp)"
            for c in agg["needed_feedback_cases"]))
    else:
        print("  feedback NOT load-bearing: every improved case best at generation 1")
    print("=" * 100 + "\n")


def main():
    ap = argparse.ArgumentParser(
        description="Multi-file validation harness over the whole mcase store")
    ap.add_argument("--cap", type=int, default=5, help="hard generation cap (loop default)")
    ap.add_argument("--plateau", type=int, default=2,
                    help="stop after this many non-improving generations (loop default)")
    ap.add_argument("--model", default=mgenerator.DEFAULT_MODEL)
    ap.add_argument("--cases", nargs="*", default=None,
                    help="subset of mcase names (default: every mcase in mcases/)")
    ap.add_argument("--out", default=str(REPORTS), help="output directory for the aggregate")
    args = ap.parse_args()

    cases = args.cases or discover_mcases()
    if not cases:
        raise SystemExit(f"no complete mcases found under {MCASES}")
    print(f"corpus: {len(cases)} mcase(s) -> {', '.join(cases)}\n")

    rows = run_benchmark(cases, args.cap, args.plateau, args.model)
    agg = aggregate(rows, args.model, args.cap, args.plateau)
    print_table(agg)

    path = write_aggregate(agg, args.out)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
