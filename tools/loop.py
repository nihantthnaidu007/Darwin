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

import generator
from evaluator import evaluate
from verify_case import BEHAVIOR_MISMATCH, TESTS_FAILED

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "cases"
RUNS = ROOT / "runs"
FLOOR_REACHED = 0.0   # weighted_cost <= 0.0 means the basket reached/beat the reference floor


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
    head = (f"REJECTED at the {ev.gate} gate ({ev.reason_code}). A rewrite that is "
            f"not correct and behavior-identical to the original is not a valid "
            f"answer, however simple it looks.")
    if ev.reason_code == BEHAVIOR_MISMATCH:
        loc = _mismatch_input(ev.feedback)
        where = f"input {loc}" if loc else "at least one input"
        return (f"{head} Your output diverged from the required behavior on {where}: "
                f"your simplification changed what the function returns there. Restore "
                f"the original behavior for that case.")
    if ev.reason_code == TESTS_FAILED:
        return (f"{head} A correctness assertion failed, so your rewrite changed "
                f"behavior for some input. Re-examine your changes for an unintended "
                f"behavior change.")
    # could-not-run / crashed / timed-out: the detail is about the candidate's own
    # code/execution (safe and useful), not the tests; forward a short tail of it.
    return f"{head} {ev.feedback.strip()[-400:]}"


def _record(gen, verdict, ev, g, feedback, improved, plateau):
    """One generation's audit record (paired with gen_NN.py on disk)."""
    rec = {"generation": gen, "verdict": verdict, "is_improvement": improved,
           "plateau_after": plateau, "feedback_given": feedback}
    if g is not None:
        rec["model"] = g.model
        rec["usage"] = {"input_tokens": g.input_tokens, "output_tokens": g.output_tokens}
        rec["cost_usd"] = g.cost_usd
    if ev is not None:
        rec.update(reason_code=ev.reason_code, gate=ev.gate,
                   weighted_cost=ev.weighted_cost, flags=ev.flags, metrics=ev.metrics)
    return rec


def run_loop(case_name, cap=5, plateau_limit=2, model=generator.DEFAULT_MODEL):
    case_dir = CASES / case_name
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    original_code = (case_dir / "original.py").read_text(encoding="utf-8")

    run_dir = RUNS / f"{case_name}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    run_dir.mkdir(parents=True, exist_ok=True)

    def checkpoint(rec):  # persist each generation immediately (crash-inspectable)
        (run_dir / f"gen_{rec['generation']:02d}.json").write_text(
            json.dumps(rec, indent=2), encoding="utf-8")

    # Generation 0: the bloated original — establishes the baseline cost and is the
    # guaranteed fallback. (It passes the gates by construction; weighted_cost == 1.0.)
    base_ev = evaluate(str(case_dir / "original.py"), case_dir)
    (run_dir / "gen_00_original.py").write_text(original_code, encoding="utf-8")
    records = [_record(0, "baseline", base_ev, None, "(baseline — the bloated original)",
                       False, 0)]
    checkpoint(records[0])

    best_code, best_ev = original_code, base_ev
    plateau, halted = 0, None
    prev_code = prev_feedback = None   # gen 1 sees only original + task (Fork 1)

    for gen in range(1, cap + 1):
        try:
            g = generator.generate(meta, original_code, prev_code, prev_feedback, model)
        except anthropic.APIError as e:        # the one halting condition
            halted = f"{e.__class__.__name__}: {e}"
            break

        (run_dir / f"gen_{gen:02d}.py").write_text(g.code or g.raw_text, encoding="utf-8")

        if not g.valid:                        # not terminal — feed the error back, continue
            plateau += 1
            rec = _record(gen, "invalid", None, g, g.error, False, plateau)
            records.append(rec); checkpoint(rec)
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
        records.append(rec); checkpoint(rec)

        if ev.verdict == "scored" and ev.weighted_cost <= FLOOR_REACHED:
            break                              # reached/beat the clean floor — done
        if plateau >= plateau_limit:
            break                              # stuck — stop
        prev_code, prev_feedback = g.code, feedback

    # Return the best gate-passing candidate; the baseline original is the fallback.
    improved_overall = best_ev.weighted_cost < base_ev.weighted_cost
    (run_dir / "best.py").write_text(best_code, encoding="utf-8")
    summary = {
        "case": case_name, "model": model,
        "config": {"cap": cap, "plateau_limit": plateau_limit},
        "baseline_weighted_cost": base_ev.weighted_cost,
        "best_weighted_cost": best_ev.weighted_cost,
        "improved_over_baseline": improved_overall,
        "returned": "best-candidate" if improved_overall else "baseline-original",
        "halted": halted,
        "generations": len(records) - 1,
        "total_input_tokens": sum(r.get("usage", {}).get("input_tokens", 0) for r in records),
        "total_output_tokens": sum(r.get("usage", {}).get("output_tokens", 0) for r in records),
        "total_cost_usd": round(sum(r.get("cost_usd", 0.0) for r in records), 6),
        "trace": records,
    }
    (run_dir / "run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary, run_dir


def _print_summary(s, run_dir):
    print("=" * 78)
    print(f"CASE {s['case']}  model={s['model']}  "
          f"(cap={s['config']['cap']}, plateau={s['config']['plateau_limit']})")
    print("=" * 78)
    for r in s["trace"]:
        g = r["generation"]
        if r["verdict"] == "baseline":
            print(f"gen {g} BASELINE  weighted_cost={r['weighted_cost']}  (bloated original)")
        elif r["verdict"] == "invalid":
            print(f"gen {g} INVALID   {r['feedback_given']}")
        elif r["verdict"] == "scored":
            star = "   <- new best" if r["is_improvement"] else ""
            print(f"gen {g} SCORED    weighted_cost={r['weighted_cost']}  flags={r['flags']}{star}")
        else:
            print(f"gen {g} REJECTED  {r['reason_code']} @ {r['gate']} gate")
        if r.get("metrics"):
            m = r["metrics"]
            print(f"          cyc_total={m['cyclomatic_total']} lloc={m['logical_loc']} "
                  f"deps={m['dependency_count']} dead={m['dead_code_count']} "
                  f"nest={m['max_nesting_depth']} mi={m['maintainability_index']}")
        if r["verdict"] in ("scored", "rejected"):
            print(f"          feedback -> {r['feedback_given'].splitlines()[0]}")
    if s["halted"]:
        print(f"\nHALTED (API failure): {s['halted']}")
    print(f"\nbaseline_cost={s['baseline_weighted_cost']}  best_cost={s['best_weighted_cost']}"
          f"  ->  returned {s['returned']}")
    print(f"generations={s['generations']}  tokens in/out="
          f"{s['total_input_tokens']}/{s['total_output_tokens']}  "
          f"cost=${s['total_cost_usd']}")
    print(f"artifacts: {run_dir}")


def main():
    ap = argparse.ArgumentParser(description="Phase 3 self-improvement loop")
    ap.add_argument("case", help="case name under cases/ (e.g. merge_intervals)")
    ap.add_argument("--cap", type=int, default=5, help="hard generation cap")
    ap.add_argument("--plateau", type=int, default=2,
                    help="stop after this many consecutive non-improving generations")
    ap.add_argument("--model", default=generator.DEFAULT_MODEL)
    args = ap.parse_args()
    if not (CASES / args.case).is_dir():
        sys.exit(f"no such case: {args.case} (looked in {CASES})")
    summary, run_dir = run_loop(args.case, args.cap, args.plateau, args.model)
    _print_summary(summary, run_dir)


if __name__ == "__main__":
    main()
