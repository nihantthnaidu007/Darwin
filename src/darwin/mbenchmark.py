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

from darwin import paths
from darwin import logsetup
from darwin import mgenerator
from darwin import mloop
from darwin import runinput
from darwin import runstate
from darwin.feedback_materiality import FEEDBACK_MATERIALITY_EPSILON_PP
from darwin.mrun_summary import summarize_mrun

ROOT = paths.data_root()
MCASES = ROOT / "mcases"
REPORTS = ROOT / "reports"
RUNS = ROOT / "runs"

log = logsetup.get_logger(
    "mbenchmark"
)  # operational log -> stderr (configured at the entry point)
# Per-case checkpoint of completed mcases (under the gitignored runs/). A fresh run
# clears this and rewrites it; --resume reads it to skip already-completed mcases.
RUN_STATE = RUNS / "mbenchmark_runstate.jsonl"

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
        if all((d / f).is_file() for f in _REQUIRED_FILES) and all(
            (d / sub).is_dir() for sub in _REQUIRED_DIRS
        ):
            found.append(d.name)
    return found


def _case_meta(case):
    """The mcase's grouping axes. mcase meta uses 'kind' (the domain descriptor,
    the multi-file analogue of single-function 'category') and 'difficulty'."""
    m = runinput.load_mcase_meta(MCASES / case)
    return m.get("kind", "?"), m.get("difficulty", "?")


def run_benchmark(
    cases,
    cap,
    plateau,
    model,
    run_loop=mloop.run_loop,
    state=None,
    resume=False,
    emitter=None,
):
    """Run the UNMODIFIED mloop over each mcase and collect its per-run summary.

    `run_loop` is an injectable seam (default mloop.run_loop) so the orchestration
    is testable with a fake loop -- no API key and no Docker. Checkpointing is
    additive: with a `state` (a runstate.RunState), a fresh run clears prior state
    and persists each mcase as it completes; with resume=True, mcases already in the
    state are skipped and their persisted summaries reused, so the assembled rows --
    and therefore the aggregate -- are the union of resumed and newly run mcases,
    identical to a complete fresh run.

    `emitter` is the verdict-emission seam threaded to the loop (a VerdictEmitter,
    decision 0032). None (the default) keeps the loop's 1.0 in-process default, so
    behavior is byte-identical; a 2.0 out-of-process emitter is injected by passing
    one, and it reaches run_loop untouched. It is forwarded only when set, so an
    injected fake run_loop keeps working unchanged.
    """
    if state is not None:
        config = runstate.run_config(model, cap, plateau)
        if resume:
            done = state.resume(config)  # fail closed if the config mismatches
        else:
            state.start(config)  # fresh run: record config, clear prior
            done = {}
    else:
        done = {}
    rows = []
    for i, case in enumerate(cases, 1):
        if case in done:  # resumed: reuse persisted result
            log.info(
                "[%s/%s] %s already complete -> skipped (resumed)",
                i,
                len(cases),
                case,
                extra={"case": case, "resumed": True},
            )
            rows.append(done[case])
            continue
        log.info(
            "[%s/%s] running mloop on %s (cap=%s, plateau=%s, model=%s) ...",
            i,
            len(cases),
            case,
            cap,
            plateau,
            model,
        )
        # Forward the verdict-emission seam only when one was injected, so the default
        # call is byte-identical to before (and an injected 4-arg fake run_loop is
        # unaffected). None lets run_loop apply its own in-process default.
        loop_kwargs = {} if emitter is None else {"emitter": emitter}
        _summary, run_dir = run_loop(
            case, cap, plateau, model, **loop_kwargs
        )  # loop UNMODIFIED
        s = summarize_mrun(run_dir)  # read its own logs
        kind, difficulty = _case_meta(case)
        s["kind"], s["difficulty"] = kind, difficulty
        if state is not None:
            state.append(case, s)  # persist the moment it completes
        rows.append(s)
        log.info(
            "      -> %s; best gen %s; bloat removed %s%%; $%s",
            s["verdict"],
            s["best_generation"],
            s["bloat_removed_pct"],
            s["total_cost_usd"],
            extra={
                "case": case,
                "model": model,
                "verdict": s["verdict"],
                "improved_over_baseline": s["improved_over_baseline"],
                "best_generation": s["best_generation"],
                "bloat_removed_pct": s["bloat_removed_pct"],
                "total_cost_usd": s["total_cost_usd"],
                "total_input_tokens": s["total_input_tokens"],
                "total_output_tokens": s["total_output_tokens"],
            },
        )
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
    needed_feedback = [
        {
            "case": r["case"],
            "best_generation": r["best_generation"],
            "first_scored_generation": r["first_scored_generation"],
            "first_pass_bloat_removed_pct": r["first_pass_bloat_removed_pct"],
            "best_bloat_removed_pct": r["bloat_removed_pct"],
            "feedback_gain_pp": r["feedback_gain_pp"],
            "structural_changes_from_first": r["structural_changes_from_first"],
        }
        for r in improved
        if r["best_generation"] >= 2
    ]
    cases = [
        {
            "case": r["case"],
            "kind": r["kind"],
            "difficulty": r["difficulty"],
            "verdict": r["verdict"],
            "improved_over_baseline": r["improved_over_baseline"],
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
            "best_flags": r["best_flags"],
            "halted": r["halted"],
            "structural_changes_from_first": r["structural_changes_from_first"],
            "per_metric": r["per_metric"],
            "run_dir": r["run_dir"],
        }
        for r in rows
    ]
    return {
        "model": model,
        "config": {"cap": cap, "plateau_limit": plateau},
        "n_cases": len(rows),
        "improved": len(improved),
        "baseline_returned": len(rows) - len(improved),
        "one_shot": len(one_shot),
        "needed_feedback": len(needed_feedback),
        "needed_feedback_cases": needed_feedback,
        # Load-bearing only if some later-generation gain CLEARS the materiality floor
        # (decision 0021); direction alone (bool(needed_feedback)) credits gains within
        # run-to-run noise, so it overpromises relative to the field's name.
        "feedback_load_bearing": any(
            c["feedback_gain_pp"] > FEEDBACK_MATERIALITY_EPSILON_PP
            for c in needed_feedback
        ),
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
    # Pre-built aligned lines are passed as a single "%s" arg so the column layout
    # and any literal "%" survive untouched; the message-only console handler then
    # renders the table exactly as the old print did (on stderr now).
    log.info("%s", "\n" + "=" * 100)
    log.info(
        "MAGGREGATE  model=%s  cap=%s plateau=%s  cases=%s",
        agg["model"],
        agg["config"]["cap"],
        agg["config"]["plateau_limit"],
        agg["n_cases"],
        extra={
            "model": agg["model"],
            "cap": agg["config"]["cap"],
            "plateau_limit": agg["config"]["plateau_limit"],
            "n_cases": agg["n_cases"],
        },
    )
    log.info("=" * 100)
    log.info(
        "%s",
        f"  {'case':<16}{'kind':<30}{'diff':<8}{'result':<16}"
        f"{'bestgen':>8}{'gens':>6}{'bloat%':>8}{'cost$':>9}",
    )
    log.info("%s", "  " + "-" * 96)
    for c in agg["cases"]:
        result = "improved" if c["improved_over_baseline"] else "baseline-kept"
        log.info(
            "%s",
            f"  {c['case']:<16}{c['kind'][:28]:<30}{c['difficulty']:<8}{result:<16}"
            f"{c['best_generation']:>8}{c['generations_attempted']:>6}"
            f"{c['bloat_removed_pct']:>8}{c['total_cost_usd']:>9}",
        )
    log.info("%s", "  " + "-" * 96)
    log.info(
        "%s",
        f"  improved {agg['improved']}/{agg['n_cases']}   "
        f"baseline-returned {agg['baseline_returned']}/{agg['n_cases']}   "
        f"one-shot {agg['one_shot']}/{agg['improved']}   "
        f"needed gen2+ {agg['needed_feedback']}/{agg['improved']}",
    )
    log.info(
        "  total cost $%s  (tokens in/out %s/%s)",
        agg["total_cost_usd"],
        agg["total_input_tokens"],
        agg["total_output_tokens"],
        extra={
            "total_cost_usd": agg["total_cost_usd"],
            "total_input_tokens": agg["total_input_tokens"],
            "total_output_tokens": agg["total_output_tokens"],
            "improved": agg["improved"],
            "n_cases": agg["n_cases"],
        },
    )
    if agg["needed_feedback_cases"]:
        log.info(
            "%s",
            "  feedback reached best at gen 2+ for: "
            + ", ".join(
                f"{c['case']}(gen{c['best_generation']}, gen1 already "
                f"{c['first_pass_bloat_removed_pct']}%, +{c['feedback_gain_pp']}pp)"
                for c in agg["needed_feedback_cases"]
            ),
        )
    else:
        log.info(
            "  feedback NOT load-bearing: every improved case best at generation 1"
        )
    log.info("%s", "=" * 100 + "\n")


def main():
    ap = argparse.ArgumentParser(
        description="Multi-file validation harness over the whole mcase store"
    )
    ap.add_argument(
        "--cap", type=int, default=5, help="hard generation cap (loop default)"
    )
    ap.add_argument(
        "--plateau",
        type=int,
        default=2,
        help="stop after this many non-improving generations (loop default)",
    )
    ap.add_argument("--model", default=mgenerator.DEFAULT_MODEL)
    ap.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="subset of mcase names (default: every mcase in mcases/)",
    )
    ap.add_argument(
        "--out", default=str(REPORTS), help="output directory for the aggregate"
    )
    ap.add_argument(
        "--mcases-dir",
        default=None,
        help="directory holding the mcases (overrides the resolved data root; pass "
        "this, or set DARWIN_DATA_ROOT, when running installed)",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="resume an interrupted run: skip mcases already recorded in run-state "
        "and run only the rest (same corpus and config). Default is a fresh "
        "run that clears prior state first.",
    )
    args = ap.parse_args()
    logsetup.configure()  # entry point: wire logging once (never at import)
    if (
        args.mcases_dir
    ):  # explicit override; feeds discover/meta here AND mloop.run_loop
        mcases_dir = Path(args.mcases_dir).resolve()
        globals()["MCASES"] = mcases_dir
        mloop.MCASES = mcases_dir

    cases = args.cases or discover_mcases()
    if not cases:
        raise SystemExit(f"no complete mcases found under {MCASES}")
    log.info(
        "corpus: %s mcase(s) -> %s%s",
        len(cases),
        ", ".join(cases),
        "  [resume]" if args.resume else "",
    )

    state = runstate.RunState(RUN_STATE)
    try:
        rows = run_benchmark(
            cases, args.cap, args.plateau, args.model, state=state, resume=args.resume
        )
    except runstate.ConfigMismatchError as e:
        raise SystemExit(str(e))  # fail closed with a clear message
    agg = aggregate(rows, args.model, args.cap, args.plateau)
    print_table(agg)

    path = write_aggregate(agg, args.out)
    log.info("wrote %s", path)


if __name__ == "__main__":
    main()
