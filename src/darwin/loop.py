"""Phase 3 orchestrator — the directed generate -> evaluate -> feedback loop.

It wires existing pieces together and adds nothing clever: the intelligence lives
in the Phase-2 evaluator (reused wholesale, never re-implemented here) and in
feeding that evaluator's feedback back into the next generation. Per run it:

  0. evaluates the bloated original as the baseline AND the guaranteed fallback;
  1. generates a candidate (gen 1: original + task; gen N>1: + previous candidate
     + sanitized feedback — Fork 1);
  2. evaluates it with the real gates + metrics (it never re-scores anything here);
  3. logs every generation (candidate, verdict, metrics, score, feedback, tokens,
     cost) to disk so a human can audit for reward hacking;
  4. stops on the hard cap, on reaching the reference floor, or on a plateau;
  5. returns the BEST gate-passing candidate found across ALL generations, or the
     baseline original if none beat it — NEVER something worse than the baseline.

A rejected or invalid generation is NOT terminal: its reason becomes feedback and
the loop continues. Only an API failure (after the SDK's retries) halts the loop.

Fork 3 / honesty: the generator never sees the tests or the golden outputs. A
SCORED candidate's feedback is metric/floor data only (safe to forward as-is). A
REJECTED candidate's raw reason can embed a golden EXPECTED output ("expected R,
got R") — format_feedback() strips that: it names the diverging INPUT (Fork 1's
"input X") but never the expected output (Fork 3).

Usage: python loop.py <case_name> [--cap N] [--plateau N] [--model ID]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from darwin import paths
from darwin import generator
from darwin import logsetup
from darwin import runinput
from darwin.evaluator import evaluate
from darwin.verify_case import BEHAVIOR_MISMATCH, TESTS_FAILED

# Data directories resolve LAZILY, never at import: the installed console scripts must
# run --help and honor --cases-dir / DARWIN_DATA_ROOT without a checkout on disk (the
# P8.3 audit found import-time resolution broke that). CASES and RUNS stay settable,
# monkeypatchable module attributes -- an explicit `loop.CASES = ...` (set by
# benchmark.py, or a test) shadows the lazy default below, because an assigned module
# global wins over module __getattr__ (PEP 562).
_THIS = sys.modules[__name__]


def __getattr__(name):
    # Reached only when `name` is not an explicitly set module attribute, so this is
    # the lazy default. Resolves at first access (inside run_loop or main), not at
    # import; raises RuntimeError via paths.data_root() when no data root is locatable.
    if name == "CASES":
        return paths.cases_dir()
    if name == "RUNS":
        return paths.runs_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


FLOOR_REACHED = (
    0.0  # weighted_cost <= 0.0 means the basket reached/beat the reference floor
)

log = logsetup.get_logger(
    "loop"
)  # operational log -> stderr (configured at the entry point)


def _mismatch_input(feedback):
    """Pull only the diverging INPUT from a golden-mismatch reason, dropping the
    expected output that follows ': expected ...' (Fork 3 — never reveal the oracle)."""
    m = re.search(r"(args=.*kwargs=.*?):\s*expected", feedback, re.DOTALL)
    return m.group(1).strip() if m else ""


def format_feedback(ev):
    """Turn an Evaluation into the next generation's feedback. Scored feedback is
    forwarded as-is (metrics + floor, no oracle). Rejected feedback is rebuilt so
    it can never leak an expected output."""
    if ev.verdict == "scored":
        return ev.feedback
    head = (
        f"REJECTED at the {ev.gate} gate ({ev.reason_code}). A rewrite that is "
        f"not correct and behavior-identical to the original is not a valid "
        f"answer, however simple it looks."
    )
    if ev.reason_code == BEHAVIOR_MISMATCH:
        loc = _mismatch_input(ev.feedback)
        where = f"input {loc}" if loc else "at least one input"
        return (
            f"{head} Your output diverged from the required behavior on {where}: "
            f"your simplification changed what the function returns there. Restore "
            f"the original behavior for that case."
        )
    if ev.reason_code == TESTS_FAILED:
        return (
            f"{head} A correctness assertion failed, so your rewrite changed "
            f"behavior for some input. Re-examine your changes for an unintended "
            f"behavior change."
        )
    # could-not-run / crashed / timed-out: the detail is about the candidate's own
    # code/execution (safe and useful), not the tests; forward a short tail of it.
    return f"{head} {ev.feedback.strip()[-400:]}"


def _record(gen, verdict, ev, g, feedback, improved, plateau):
    """One generation's audit record (paired with gen_NN.py on disk)."""
    rec = {
        "generation": gen,
        "verdict": verdict,
        "is_improvement": improved,
        "plateau_after": plateau,
        "feedback_given": feedback,
    }
    if g is not None:
        rec["model"] = g.model
        rec["usage"] = {
            "input_tokens": g.input_tokens,
            "output_tokens": g.output_tokens,
        }
        rec["cost_usd"] = g.cost_usd
    if ev is not None:
        rec.update(
            reason_code=ev.reason_code,
            gate=ev.gate,
            weighted_cost=ev.weighted_cost,
            flags=ev.flags,
            metrics=ev.metrics,
        )
    return rec


def run_loop(case_name, cap=5, plateau_limit=2, model=generator.DEFAULT_MODEL):
    case_dir = _THIS.CASES / case_name
    meta = runinput.load_case_meta(case_dir)
    original_code = (case_dir / "original.py").read_text(encoding="utf-8")

    run_dir = _THIS.RUNS / f"{case_name}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    run_dir.mkdir(parents=True, exist_ok=True)

    def checkpoint(rec):  # persist each generation immediately (crash-inspectable)
        (run_dir / f"gen_{rec['generation']:02d}.json").write_text(
            json.dumps(rec, indent=2), encoding="utf-8"
        )

    # Generation 0: the bloated original — establishes the baseline cost and is the
    # guaranteed fallback. (It passes the gates by construction; weighted_cost == 1.0.)
    base_ev = evaluate(str(case_dir / "original.py"), case_dir)
    (run_dir / "gen_00_original.py").write_text(original_code, encoding="utf-8")
    records = [
        _record(
            0, "baseline", base_ev, None, "(baseline — the bloated original)", False, 0
        )
    ]
    checkpoint(records[0])

    best_code, best_ev = original_code, base_ev
    plateau, halted = 0, None
    prev_code = prev_feedback = None  # gen 1 sees only original + task (Fork 1)

    for gen in range(1, cap + 1):
        try:
            g = generator.generate(meta, original_code, prev_code, prev_feedback, model)
        except anthropic.APIError as e:  # the one halting condition
            halted = f"{e.__class__.__name__}: {e}"
            break

        (run_dir / f"gen_{gen:02d}.py").write_text(
            g.code or g.raw_text, encoding="utf-8"
        )

        if not g.valid:  # not terminal — feed the error back, continue
            plateau += 1
            rec = _record(gen, "invalid", None, g, g.error, False, plateau)
            records.append(rec)
            checkpoint(rec)
            prev_code, prev_feedback = g.code or g.raw_text, g.error
            if plateau >= plateau_limit:
                break
            continue

        ev = evaluate(str(run_dir / f"gen_{gen:02d}.py"), case_dir)
        feedback = format_feedback(ev)
        improved = ev.verdict == "scored" and ev.weighted_cost < best_ev.weighted_cost
        if improved:
            best_code, best_ev, plateau = g.code, ev, 0
        else:
            plateau += 1
        rec = _record(gen, ev.verdict, ev, g, feedback, improved, plateau)
        records.append(rec)
        checkpoint(rec)

        if ev.verdict == "scored" and ev.weighted_cost <= FLOOR_REACHED:
            break  # reached/beat the clean floor — done
        if plateau >= plateau_limit:
            break  # stuck — stop
        prev_code, prev_feedback = g.code, feedback

    # Return the best gate-passing candidate; the baseline original is the fallback.
    improved_overall = best_ev.weighted_cost < base_ev.weighted_cost
    (run_dir / "best.py").write_text(best_code, encoding="utf-8")
    summary = {
        "case": case_name,
        "model": model,
        "config": {"cap": cap, "plateau_limit": plateau_limit},
        # Request provenance: read from the generator's own request configuration
        # (not re-typed here) so the recorded config equals what was sent (decision 0022).
        "provenance": generator.request_provenance(model),
        "baseline_weighted_cost": base_ev.weighted_cost,
        "best_weighted_cost": best_ev.weighted_cost,
        "improved_over_baseline": improved_overall,
        "returned": "best-candidate" if improved_overall else "baseline-original",
        "halted": halted,
        "generations": len(records) - 1,
        "total_input_tokens": sum(
            r.get("usage", {}).get("input_tokens", 0) for r in records
        ),
        "total_output_tokens": sum(
            r.get("usage", {}).get("output_tokens", 0) for r in records
        ),
        "total_cost_usd": round(sum(r.get("cost_usd", 0.0) for r in records), 6),
        "trace": records,
    }
    (run_dir / "run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary, run_dir


def _log_summary(s, run_dir):
    """Emit the per-run trace as operational log records. The console handler is
    message-only, so the aligned block renders exactly as the old print did (on
    stderr now); key run facts ride along as structured `extra` fields for the JSON
    handler. Same values as before -- only the output mechanism changed."""
    log.info("=" * 78)
    log.info(
        "CASE %s  model=%s  (cap=%s, plateau=%s)",
        s["case"],
        s["model"],
        s["config"]["cap"],
        s["config"]["plateau_limit"],
        extra={
            "case": s["case"],
            "model": s["model"],
            "cap": s["config"]["cap"],
            "plateau_limit": s["config"]["plateau_limit"],
        },
    )
    log.info("=" * 78)
    for r in s["trace"]:
        g = r["generation"]
        if r["verdict"] == "baseline":
            log.info(
                "gen %s BASELINE  weighted_cost=%s  (bloated original)",
                g,
                r["weighted_cost"],
            )
        elif r["verdict"] == "invalid":
            log.info("gen %s INVALID   %s", g, r["feedback_given"])
        elif r["verdict"] == "scored":
            star = "   <- new best" if r["is_improvement"] else ""
            log.info(
                "gen %s SCORED    weighted_cost=%s  flags=%s%s",
                g,
                r["weighted_cost"],
                r["flags"],
                star,
                extra={
                    "generation": g,
                    "verdict": "scored",
                    "weighted_cost": r["weighted_cost"],
                    "flags": r["flags"],
                    "is_improvement": r["is_improvement"],
                },
            )
        else:
            log.info(
                "gen %s REJECTED  %s @ %s gate",
                g,
                r["reason_code"],
                r["gate"],
                extra={
                    "generation": g,
                    "verdict": "rejected",
                    "reason_code": r["reason_code"],
                    "gate": r["gate"],
                },
            )
        if r.get("metrics"):
            m = r["metrics"]
            log.info(
                "          cyc_total=%s lloc=%s deps=%s dead=%s nest=%s mi=%s",
                m["cyclomatic_total"],
                m["logical_loc"],
                m["dependency_count"],
                m["dead_code_count"],
                m["max_nesting_depth"],
                m["maintainability_index"],
            )
        if r["verdict"] in ("scored", "rejected"):
            log.info("          feedback -> %s", r["feedback_given"].splitlines()[0])
    if s["halted"]:
        log.warning(
            "\nHALTED (API failure): %s", s["halted"], extra={"halted": s["halted"]}
        )
    log.info(
        "\nbaseline_cost=%s  best_cost=%s  ->  returned %s",
        s["baseline_weighted_cost"],
        s["best_weighted_cost"],
        s["returned"],
        extra={
            "case": s["case"],
            "returned": s["returned"],
            "improved_over_baseline": s["improved_over_baseline"],
            "baseline_weighted_cost": s["baseline_weighted_cost"],
            "best_weighted_cost": s["best_weighted_cost"],
        },
    )
    log.info(
        "generations=%s  tokens in/out=%s/%s  cost=$%s",
        s["generations"],
        s["total_input_tokens"],
        s["total_output_tokens"],
        s["total_cost_usd"],
        extra={
            "model": s["model"],
            "generations": s["generations"],
            "total_input_tokens": s["total_input_tokens"],
            "total_output_tokens": s["total_output_tokens"],
            "total_cost_usd": s["total_cost_usd"],
            "halted": s["halted"],
        },
    )
    log.info("artifacts: %s", run_dir)


def main():
    ap = argparse.ArgumentParser(description="Phase 3 self-improvement loop")
    ap.add_argument("case", help="case name under cases/ (e.g. merge_intervals)")
    ap.add_argument("--cap", type=int, default=5, help="hard generation cap")
    ap.add_argument(
        "--plateau",
        type=int,
        default=2,
        help="stop after this many consecutive non-improving generations",
    )
    ap.add_argument("--model", default=generator.DEFAULT_MODEL)
    ap.add_argument(
        "--cases-dir",
        default=None,
        help="directory holding the cases (overrides the resolved data root; pass "
        "this, or set DARWIN_DATA_ROOT, when running installed)",
    )
    args = ap.parse_args()
    logsetup.configure()  # entry point: wire logging once (never at import)
    if args.cases_dir:  # explicit override; feeds the case lookup below and run_loop
        globals()["CASES"] = Path(args.cases_dir).resolve()
    try:
        # Resolve the data dirs now (after argparse, honoring any override above): a
        # clean, actionable exit when installed without a locatable data root, never an
        # import-time crash or a mid-run traceback. Concrete-ize them so run_loop reuses
        # the resolved values.
        globals()["CASES"] = _THIS.CASES
        globals()["RUNS"] = _THIS.RUNS
    except RuntimeError as e:
        raise SystemExit(str(e))
    if not (_THIS.CASES / args.case).is_dir():
        sys.exit(f"no such case: {args.case} (looked in {_THIS.CASES})")
    summary, run_dir = run_loop(args.case, args.cap, args.plateau, args.model)
    _log_summary(summary, run_dir)


if __name__ == "__main__":
    main()
