"""Phase V2 multi-file orchestrator — the directed generate -> evaluate -> feedback
loop for a MULTI-FILE unit. The multi-file analogue of tools/loop.py: it wires
mgenerator and mevaluator together and adds nothing clever. The intelligence lives
in mgenerator (the rewrite) and mevaluator (the objective gates + score); the loop
only wires them, sanitizes feedback, and records the trace honestly. Per run it:

  0. evaluates the bloated original unit as the baseline AND the guaranteed
     fallback (it passes the gates by construction; weighted_cost == 1.0);
  1. generates a candidate (gen 1: original + task; gen N>1: + previous candidate
     + sanitized feedback -- Fork 1);
  2. materializes the candidate into its OWN fresh per-generation directory and
     evaluates it through the real container gates + metrics (never re-scored here);
  3. logs every generation immediately to disk (candidate package, verdict, gate,
     reason_code, weighted_cost, is_improvement, flags, metrics, usage, cost, and
     the exact feedback given) so the load-bearing question can be answered from
     the trace, and a human can audit for reward hacking;
  4. stops on the hard cap, on reaching the reference floor, or on a plateau;
  5. returns the BEST gate-passing candidate found across ALL generations, or the
     baseline original if none beat it -- NEVER something worse than the baseline.

A rejected or invalid generation is NOT terminal: its sanitized reason becomes the
next generation's feedback and the loop continues. Only an mgenerator API failure
(after the SDK's retries) halts the loop.

FLAG 1 (feedback honesty). mevaluator's feedback embeds the oracle in two places:
the `original :` outcome line of an equivalence rejection, and the pytest dump of a
tests-failed rejection. format_feedback() re-sanitizes before any feedback reaches
the generator (Fork 3): a SCORED candidate's feedback is metric/floor data only
(forwarded as-is); an equivalence rejection names only the diverging INPUT (Fork 1)
and never the oracle's outcome; a tests-failed rejection is replaced by a generic
behavior-changed message (never the dump); a could-not-run / crashed / timed-out
rejection forwards a short tail of the candidate's OWN error (no oracle).

FLAG 2 (directory hygiene). mgenerator.materialize does not clean a pre-existing
directory, so each generation is materialized into its own FRESH directory under
the run dir and no directory is ever reused across generations.

Usage: python mloop.py <case_name> [--cap N] [--plateau N] [--model ID]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

import logsetup
import mevaluator
import mgenerator
import runinput
from generator import request_provenance  # mgenerator reuses generator's request config
from verify_case import TESTS_FAILED

ROOT = Path(__file__).resolve().parent.parent
MCASES = ROOT / "mcases"
RUNS = ROOT / "runs"
FLOOR_REACHED = 0.0   # weighted_cost <= 0.0 means the basket reached/beat the reference floor

log = logsetup.get_logger("mloop")  # operational log -> stderr (configured at the entry point)


# ---------------------------------------------------------------- feedback

def _equivalence_feedback(ev):
    """Re-sanitize an equivalence rejection. Keep the head and the `First diverging
    sequence ...` line (the diverging INPUT -- naming the sequence and the call is
    what Fork 1 permits) and, on a fail-closed rejection, the candidate's OWN replay
    error. DROP the `original :` line (the oracle's outcome -- Fork 3) and the
    `candidate:` line, the only places mevaluator prints an outcome value."""
    kept = [line for line in ev.feedback.splitlines()
            if not line.strip().startswith(("original :", "candidate:"))]
    return "\n".join(kept)


def format_feedback(ev):
    """Turn an MEvaluation into the next generation's feedback, sanitized so no
    oracle outcome can leak (FLAG 1). The loop owns this; mevaluator's richer
    feedback is never forwarded raw for a rejection."""
    if ev.verdict == "scored":
        return ev.feedback                      # structural metrics + floor only, no oracle
    if ev.gate == "equivalence":
        return _equivalence_feedback(ev)
    # ev.gate == "tests"
    head = (f"REJECTED at the {ev.gate} gate ({ev.reason_code}). A rewrite that is "
            f"not correct and behavior-identical to the original is not a valid "
            f"answer, however simple it looks.")
    if ev.reason_code == TESTS_FAILED:
        # NEVER forward the pytest dump: a failing assertion can print the oracle's
        # expected value. Emit a generic behavior-changed message only.
        return (f"{head} A correctness assertion failed inside the container, so your "
                f"rewrite changed the unit's behavior for some input. Re-examine your "
                f"changes for an unintended behavior change.")
    # could-not-run / crashed / timed-out: the detail is the candidate's OWN code or
    # execution failing (import error, a missing subpackage __init__, a crash, a
    # timeout), which carries no oracle -- forward a short tail.
    return f"{head} {ev.feedback.strip()[-400:]}"


# ------------------------------------------------------------- recording

def _record(gen, verdict, ev, g, feedback, improved, plateau, candidate_dir):
    """One generation's audit record (paired with its candidate dir on disk)."""
    rec = {"generation": gen, "verdict": verdict, "is_improvement": improved,
           "plateau_after": plateau, "feedback_given": feedback,
           "candidate_dir": candidate_dir}
    if g is not None:
        rec["model"] = g.model
        rec["usage"] = {"input_tokens": g.input_tokens, "output_tokens": g.output_tokens}
        rec["cost_usd"] = g.cost_usd
    if ev is not None:
        rec.update(reason_code=ev.reason_code, gate=ev.gate,
                   weighted_cost=ev.weighted_cost, flags=ev.flags, metrics=ev.metrics)
    return rec


# ---------------------------------------------------------------- loop

def run_loop(case_name, cap=5, plateau_limit=2, model=mgenerator.DEFAULT_MODEL,
             client=None, generate=mgenerator.generate, evaluate=mevaluator.evaluate,
             run_root=None, timeout=30.0):
    """Drive one mcase through the directed loop. `generate` and `evaluate` are
    injectable seams (default the real mgenerator / mevaluator) so the orchestration
    and the feedback sanitizer are testable with no API key and no Docker."""
    case_dir = MCASES / case_name
    meta = runinput.load_mcase_meta(case_dir)
    original_files = mgenerator.read_unit(case_dir / "original")

    run_dir = Path(run_root or RUNS) / f"{case_name}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    run_dir.mkdir(parents=True, exist_ok=True)

    def checkpoint(rec):  # persist each generation immediately (crash-inspectable)
        (run_dir / f"gen_{rec['generation']:02d}.json").write_text(
            json.dumps(rec, indent=2), encoding="utf-8")

    # Generation 0: the bloated original -- establishes the baseline cost and is the
    # guaranteed fallback. Materialized to its own dir for a self-contained trace.
    base_dir = mgenerator.materialize(original_files, run_dir / "gen_00_baseline")
    base_ev = evaluate(case_dir, base_dir, timeout)
    records = [_record(0, "baseline", base_ev, None, "(baseline -- the bloated original)",
                       False, 0, str(base_dir))]
    checkpoint(records[0])

    best_files, best_ev = original_files, base_ev
    plateau, halted = 0, None
    prev_files = prev_feedback = None   # gen 1 sees only original + task (Fork 1)

    for gen in range(1, cap + 1):
        try:
            g = generate(meta, original_files, prev_files, prev_feedback,
                         model=model, client=client)
        except anthropic.APIError as e:        # the one halting condition
            halted = f"{e.__class__.__name__}: {e}"
            break

        if not g.valid:                        # not terminal -- feed the error back, continue
            plateau += 1
            rec = _record(gen, "invalid", None, g, g.error, False, plateau, None)
            records.append(rec); checkpoint(rec)
            prev_files, prev_feedback = g.files, g.error
            if plateau >= plateau_limit:
                break
            continue

        # FLAG 2: a FRESH directory per generation, never reused, so no stale file
        # from a prior generation can linger into this evaluation.
        cand_dir = mgenerator.materialize(g.files, run_dir / f"gen_{gen:02d}_candidate")
        ev = evaluate(case_dir, cand_dir, timeout)
        feedback = format_feedback(ev)
        improved = (ev.verdict == "scored" and ev.weighted_cost is not None
                    and ev.weighted_cost < best_ev.weighted_cost)
        if improved:
            best_files, best_ev, plateau = g.files, ev, 0
        else:
            plateau += 1
        rec = _record(gen, ev.verdict, ev, g, feedback, improved, plateau, str(cand_dir))
        records.append(rec); checkpoint(rec)

        if ev.verdict == "scored" and ev.weighted_cost is not None \
                and ev.weighted_cost <= FLOOR_REACHED:
            break                              # reached/beat the clean floor -- done
        if plateau >= plateau_limit:
            break                              # stuck -- stop
        prev_files, prev_feedback = g.files, feedback

    # Return the best gate-passing candidate; the baseline original is the fallback.
    improved_overall = (best_ev.weighted_cost is not None
                        and base_ev.weighted_cost is not None
                        and best_ev.weighted_cost < base_ev.weighted_cost)
    best_dir = mgenerator.materialize(best_files, run_dir / "best")
    summary = {
        "case": case_name, "model": model,
        "config": {"cap": cap, "plateau_limit": plateau_limit},
        # Request provenance: read from the generator's own request configuration
        # (not re-typed here) so the recorded config equals what was sent (decision 0022).
        # mgenerator reuses generator's request_kwargs, so generator's provenance
        # describes exactly what this loop's generator sent.
        "provenance": request_provenance(model),
        "baseline_weighted_cost": base_ev.weighted_cost,
        "best_weighted_cost": best_ev.weighted_cost,
        "improved_over_baseline": improved_overall,
        "returned": "best-candidate" if improved_overall else "baseline-original",
        "best_dir": str(best_dir),
        "halted": halted,
        "generations": len(records) - 1,
        "total_input_tokens": sum(r.get("usage", {}).get("input_tokens", 0) for r in records),
        "total_output_tokens": sum(r.get("usage", {}).get("output_tokens", 0) for r in records),
        "total_cost_usd": round(sum(r.get("cost_usd", 0.0) for r in records), 6),
        "trace": records,
    }
    (run_dir / "run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary, run_dir


# ---------------------------------------------------------------- CLI

def _log_summary(s, run_dir):
    """Emit the per-run trace as operational log records (message-only console, so
    the aligned block renders as before on stderr; key facts attached as structured
    `extra` fields). Same values as the old print path -- only the mechanism changed."""
    log.info("=" * 78)
    log.info("CASE %s  model=%s  (cap=%s, plateau=%s)",
             s["case"], s["model"], s["config"]["cap"], s["config"]["plateau_limit"],
             extra={"case": s["case"], "model": s["model"],
                    "cap": s["config"]["cap"], "plateau_limit": s["config"]["plateau_limit"]})
    log.info("=" * 78)
    for r in s["trace"]:
        g = r["generation"]
        if r["verdict"] == "baseline":
            log.info("gen %s BASELINE  weighted_cost=%s  (bloated original)",
                     g, r["weighted_cost"])
        elif r["verdict"] == "invalid":
            log.info("gen %s INVALID   %s", g, r["feedback_given"])
        elif r["verdict"] == "scored":
            star = "   <- new best" if r["is_improvement"] else ""
            log.info("gen %s SCORED    weighted_cost=%s  flags=%s%s",
                     g, r["weighted_cost"], r["flags"], star,
                     extra={"generation": g, "verdict": "scored",
                            "weighted_cost": r["weighted_cost"], "flags": r["flags"],
                            "is_improvement": r["is_improvement"]})
        else:
            log.info("gen %s REJECTED  %s @ %s gate", g, r["reason_code"], r["gate"],
                     extra={"generation": g, "verdict": "rejected",
                            "reason_code": r["reason_code"], "gate": r["gate"]})
        if r["verdict"] in ("scored", "rejected"):
            log.info("          feedback -> %s", r["feedback_given"].splitlines()[0])
    if s["halted"]:
        log.warning("\nHALTED (API failure): %s", s["halted"], extra={"halted": s["halted"]})
    log.info("\nbaseline_cost=%s  best_cost=%s  ->  returned %s",
             s["baseline_weighted_cost"], s["best_weighted_cost"], s["returned"],
             extra={"case": s["case"], "returned": s["returned"],
                    "improved_over_baseline": s["improved_over_baseline"],
                    "baseline_weighted_cost": s["baseline_weighted_cost"],
                    "best_weighted_cost": s["best_weighted_cost"]})
    log.info("generations=%s  tokens in/out=%s/%s  cost=$%s",
             s["generations"], s["total_input_tokens"], s["total_output_tokens"],
             s["total_cost_usd"],
             extra={"model": s["model"], "generations": s["generations"],
                    "total_input_tokens": s["total_input_tokens"],
                    "total_output_tokens": s["total_output_tokens"],
                    "total_cost_usd": s["total_cost_usd"], "halted": s["halted"]})
    log.info("artifacts: %s", run_dir)


def main():
    ap = argparse.ArgumentParser(description="Phase V2 multi-file self-improvement loop")
    ap.add_argument("case", help="case name under mcases/ (e.g. rate_limiter)")
    ap.add_argument("--cap", type=int, default=5, help="hard generation cap")
    ap.add_argument("--plateau", type=int, default=2,
                    help="stop after this many consecutive non-improving generations")
    ap.add_argument("--model", default=mgenerator.DEFAULT_MODEL)
    args = ap.parse_args()
    logsetup.configure()   # entry point: wire logging once (never at import)
    if not (MCASES / args.case).is_dir():
        sys.exit(f"no such mcase: {args.case} (looked in {MCASES})")
    summary, run_dir = run_loop(args.case, args.cap, args.plateau, args.model)
    _log_summary(summary, run_dir)


if __name__ == "__main__":
    main()
