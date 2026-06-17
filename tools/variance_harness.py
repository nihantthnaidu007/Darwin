"""P5.3 variance harness: persist each multi-file run's aggregate as a committed
snapshot and DERIVE the variance dataset (reports/mvariance.json) from those
snapshots, so the run-to-run variance result stops being hand-recorded.

Two modes:
  derive  -- read every maggregate.json snapshot under a snapshot directory
             (default reports/variance_runs) and compute the mvariance dataset:
             per case, the arrays across runs of best_generation,
             gen1_bloat_removed_pct, feedback_gain_pp, and best_bloat_removed_pct,
             plus the one_shot / needed_feedback counts and the computable summary
             facts. Pure file IO and arithmetic: NO model call, NO mbenchmark run.
  run     -- orchestrate N multi-file benchmark runs, each writing its
             maggregate.json into a distinct committed snapshot path under the
             snapshot directory (via mbenchmark's existing --out), then derive.
             RUNNING THIS SPENDS API BUDGET (P5.3b); it is built here and unit-tested
             with a stubbed runner, but is NOT executed in P5.3a.

Standard library only; mbenchmark.py is not modified (run mode shells out to it).

Usage:
  python variance_harness.py derive [--snapshots DIR] [--out FILE] [--mresults]
  python variance_harness.py run --n N [--snapshots DIR] [--cap C] [--plateau P] [--model ID]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
SNAPSHOT_DIR = REPORTS / "variance_runs"
SNAPSHOT_NAME = "maggregate.json"          # mbenchmark.write_aggregate's fixed filename
MVARIANCE = REPORTS / "mvariance.json"
# Matches mbenchmark's --out default model; run mode passes --model through explicitly.
DEFAULT_MODEL = "claude-opus-4-8"

# Per-case field rename. Each snapshot is a maggregate.json (mbenchmark.aggregate
# output); for every case in its cases[] we read these four fields and rename two to
# the mvariance dataset's field names. gen1_bloat_removed_pct is generation 1 alone
# (the snapshot's first_pass_bloat_removed_pct); best_bloat_removed_pct is the
# returned best (the snapshot's cases[] calls it bloat_removed_pct). The mvariance
# field order below is the order the committed reports/mvariance.json uses.
SNAPSHOT_TO_MVARIANCE = {
    "best_generation": "best_generation",
    "first_pass_bloat_removed_pct": "gen1_bloat_removed_pct",
    "feedback_gain_pp": "feedback_gain_pp",
    "bloat_removed_pct": "best_bloat_removed_pct",
}


# ----------------------------------------------------------------- derive

def _load_snapshots(snapshot_dir):
    """Every maggregate.json under snapshot_dir, sorted by its path relative to that
    directory (a stable key), so derive is order-stable and reruns are byte-identical."""
    snapshot_dir = Path(snapshot_dir)
    paths = sorted(snapshot_dir.rglob(SNAPSHOT_NAME),
                   key=lambda p: str(p.relative_to(snapshot_dir)))
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def _case_index(snapshot):
    """{case_name: cases[] entry} for one snapshot."""
    return {c["case"]: c for c in snapshot["cases"]}


def _findings(cases, improved_per_run, n_runs, n_cases):
    """The computable summary facts, formatted as the stable/unstable finding strings
    the mvariance structure carries. Every number is derived, not asserted by hand."""
    gen1_all = [v for c in cases.values() for v in c["gen1_bloat_removed_pct"]]
    gain_all = [v for c in cases.values() for v in c["feedback_gain_pp"]]
    case_runs = n_runs * n_cases
    improved_count = sum(improved_per_run)
    regressions = case_runs - improved_count
    all_one_shot_runs = sum(
        1 for i in range(n_runs)
        if all(c["best_generation"][i] == 1 for c in cases.values()))
    stable = [
        (f"Across {n_runs} runs x {n_cases} cases ({case_runs} case-runs), "
         f"{improved_count} improved over baseline and {regressions} returned baseline "
         f"(no improvement)."),
        (f"Generation 1 alone removed {min(gen1_all):g} to {max(gen1_all):g} percent of "
         f"the original-to-floor span across every case and run."),
    ]
    unstable = [
        (f"{all_one_shot_runs} of {n_runs} runs had all {n_cases} cases one-shot "
         f"(best generation 1)."),
        (f"feedback_gain_pp ranged from {min(gain_all):g} to {max(gain_all):g} "
         f"percentage points across cases and runs."),
    ]
    return stable, unstable


def _derived_note(n_runs):
    return (f"Derived by tools/variance_harness.py from {n_runs} maggregate.json "
            f"snapshot(s) under reports/variance_runs/. Reproducible: re-run "
            f"`python variance_harness.py derive` on the same snapshots for a "
            f"byte-identical dataset.")


def derive(snapshot_dir=SNAPSHOT_DIR):
    """Compute the mvariance dataset from the snapshots under snapshot_dir, in the
    same structure reports/mvariance.json uses. Pure and deterministic: snapshots are
    read in a stable order and case keys are sorted, so a rerun on the same snapshots
    is byte-identical."""
    snapshots = _load_snapshots(snapshot_dir)
    if not snapshots:
        raise SystemExit(f"no {SNAPSHOT_NAME} snapshots under {snapshot_dir}")
    n_runs = len(snapshots)
    indexed = [_case_index(s) for s in snapshots]
    case_names = sorted({name for idx in indexed for name in idx})

    cases, improved_per_run = {}, []
    for name in case_names:
        entries = []
        for idx in indexed:
            if name not in idx:
                raise SystemExit(f"case {name!r} is missing from a snapshot; the "
                                 f"snapshot set must cover the same cases every run.")
            entries.append(idx[name])
        arrays = {mv: [e[snap] for e in entries]
                  for snap, mv in SNAPSHOT_TO_MVARIANCE.items()}
        best_gen = arrays["best_generation"]
        cases[name] = {
            **arrays,
            "one_shot_runs": sum(1 for g in best_gen if g == 1),
            "needed_feedback_runs": sum(1 for g in best_gen if g >= 2),
        }
        improved_per_run += [bool(e["improved_over_baseline"]) for e in entries]

    stable, unstable = _findings(cases, improved_per_run, n_runs, len(case_names))
    return {
        "note": _derived_note(n_runs),
        "model": snapshots[0]["model"],
        "config": snapshots[0]["config"],
        "n_runs": n_runs,
        "cases": cases,
        "stable_findings": stable,
        "unstable_findings": unstable,
    }


def format_mresults_rows(dataset):
    """The MRESULTS six-run variance table rows, derived from the same dataset:
    `| case | best generation | one-shot | feedback_gain_pp range |`."""
    n = dataset["n_runs"]
    rows = []
    for case in sorted(dataset["cases"]):
        c = dataset["cases"][case]
        best_gen = ", ".join(str(g) for g in c["best_generation"])
        gains = c["feedback_gain_pp"]
        rows.append(f"| `{case}` | {best_gen} | {c['one_shot_runs']}/{n} | "
                    f"{min(gains):g} to {max(gains):g} |")
    return rows


# -------------------------------------------------------------------- run

def _mbenchmark_runner(out_dir, *, cap, plateau, model):
    """Invoke the UNMODIFIED mbenchmark.py for ONE run, writing its maggregate.json
    into out_dir via mbenchmark's existing --out. Shells out so this harness adds no
    engine. THIS SPENDS API BUDGET and runs the model; only run mode's authorized
    caller (P5.3b) invokes it. Returns the snapshot path it produced."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("mbenchmark.py")),
         "--out", str(out_dir), "--cap", str(cap), "--plateau", str(plateau),
         "--model", model],
        check=True)
    return out_dir / SNAPSHOT_NAME


def run(n_runs, snapshot_dir=SNAPSHOT_DIR, *, cap=5, plateau=2,
        model=DEFAULT_MODEL, runner=_mbenchmark_runner):
    """Orchestrate n_runs multi-file benchmark runs into distinct committed snapshot
    paths (run_00, run_01, ...) under snapshot_dir, then derive. `runner` is an
    injectable seam (default the real mbenchmark invocation) so the orchestration is
    unit-tested with a stub that writes a fixture instead of calling the model.
    Returns (dataset, written_paths)."""
    snapshot_dir = Path(snapshot_dir)
    written = []
    for i in range(n_runs):
        out_dir = snapshot_dir / f"run_{i:02d}"
        written.append(Path(runner(out_dir, cap=cap, plateau=plateau, model=model)))
    return derive(snapshot_dir), written


# -------------------------------------------------------------------- CLI

def _write_dataset(dataset, out_path):
    Path(out_path).write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Multi-file variance harness (P5.3)")
    sub = ap.add_subparsers(dest="mode", required=True)

    d = sub.add_parser("derive", help="derive mvariance.json from committed snapshots")
    d.add_argument("--snapshots", default=str(SNAPSHOT_DIR))
    d.add_argument("--out", default=str(MVARIANCE))
    d.add_argument("--mresults", action="store_true",
                   help="also print the MRESULTS variance table rows")

    r = sub.add_parser("run", help="AUTHORIZED SPEND (P5.3b): run N benchmarks, then derive")
    r.add_argument("--n", type=int, required=True, help="number of runs to orchestrate")
    r.add_argument("--snapshots", default=str(SNAPSHOT_DIR))
    r.add_argument("--out", default=str(MVARIANCE))
    r.add_argument("--cap", type=int, default=5)
    r.add_argument("--plateau", type=int, default=2)
    r.add_argument("--model", default=DEFAULT_MODEL)

    args = ap.parse_args()
    if args.mode == "derive":
        dataset = derive(args.snapshots)
    else:
        dataset, written = run(args.n, args.snapshots, cap=args.cap,
                               plateau=args.plateau, model=args.model)
        print(f"orchestrated {len(written)} run(s); wrote "
              f"{len(written)} snapshot(s) under {args.snapshots}")
    _write_dataset(dataset, args.out)
    print(f"wrote {args.out}")
    if getattr(args, "mresults", False):
        print("\n".join(format_mresults_rows(dataset)))


if __name__ == "__main__":
    main()
