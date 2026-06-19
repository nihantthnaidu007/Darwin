"""The evaluator (the moat). Scores ONE candidate against ONE case, objectively,
with no LLM anywhere. Three layers in strict order of authority:

  Layer 1  Correctness gate  — does the test suite pass? (hard, blocking)
  Layer 2  Behavior gate     — does it reproduce the golden I/O exactly? (blocking)
  Layer 3  Complexity score  — only for candidates that cleared 1 and 2.

Layers 1 and 2 are delegated wholesale to verify_case.classify() (which runs the
sandbox); this file does NOT re-run pytest or replay golden I/O. Layer 3 uses
freeze_metrics.freeze() for the metric basket. A candidate that fails a gate is
NOT scored — a broken answer is not a valid answer, however clean it looks. Layer
3 can never promote a candidate past a gate.

Layer 3 here implements Method A (weighted sum), the per-candidate absolute score.
Method B (Pareto) is set-relative and lives in the bake-off harness. See bakeoff.py
for the comparison and the recommendation.

Usage: python evaluator.py <candidate.py> <case_dir>
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from darwin import logsetup
from darwin import runinput
from darwin.freeze_metrics import freeze
from darwin.verify_case import classify

log = logsetup.get_logger(
    "evaluator"
)  # operational log -> stderr (configured at the entry point)

# --- Method A: weighted sum -------------------------------------------------
#
# Each metric is normalized to a cost in [0,1] anchored to THIS case:
#   original baseline value -> 1.0 (fully bloated, worst)
#   reference_floor value   -> 0.0 (clean target, best)
# so the score is a single "how bloated, on this case's own scale" number; lower
# is better. Anchoring to the floor (not to zero) matters: e.g. dead_code_count's
# floor is 1, because vulture flags the entry point itself as unused.
#
# Weights are an explicit value judgment (Method A's known weakness). They are
# chosen so the score CANNOT be gamed by fragmentation — splitting one function
# into many lowers per-function `cyclomatic_max` but not `cyclomatic_total` or
# `logical_loc`, so we weight the totals heavily and `cyclomatic_max` lightly:
#
# maintainability_index is DROPPED from scoring (weight 0, informational only). An
# independent audit showed it is gameable by cosmetics at single-function scale:
# adding a docstring/comments or lengthening variable names raises radon's MI even
# when the algorithm is byte-for-byte identical and NO real complexity was removed,
# so cosmetic padding could score as "improvement" (on income_tax a padded copy of
# the reference scored BELOW the clean floor). The structural metrics below are NOT
# gameable that way — a docstring changes none of them — so they carry the score; MI
# is still computed and logged in the basket for human observability, never scored.
WEIGHTS = {
    "cyclomatic_total": 3.0,  # total branching; fragmentation does NOT reduce it
    "logical_loc": 2.0,  # total logical lines; fragmentation INCREASES it
    "maintainability_index": 0.0,  # DROPPED: cosmetic-gameable at fn scale (see note); informational only
    "max_nesting_depth": 1.0,  # the "deeply nested" bloat pattern
    "dependency_count": 1.0,  # unnecessary imports (a core bloat category)
    "dead_code_count": 1.0,  # dead helpers (a core bloat category)
    "cyclomatic_max": 0.5,  # LOW on purpose: this is what fragmentation games
    "source_loc": 0.0,  # dropped: near-duplicate of logical_loc, no double count
}
HIGHER_BETTER = {
    "maintainability_index"
}  # up-is-good metric — but weight 0 now (informational only)


def _cost(metric, cand, orig, floor):
    """Normalized cost for one metric, or None when this case gives it no signal.

    Signal requires the original to be strictly WORSE than the reference floor on
    this metric, so the original-to-floor improvement span (den) is strictly
    positive. That reading holds in both branches: lower-is-better "worse" is a
    higher value (den = orig - floor), higher-is-better "worse" is a lower value
    (den = floor - orig). When that span is zero (original == floor, nothing to
    improve) OR inverted (original already better than the floor, den < 0), there
    is nothing to normalize against; dividing would flip the sign so a candidate
    worse than both anchors would score below the floor. The existing "no signal,
    do not divide" rule therefore extends from den == 0 to den <= 0: we return
    None and weighted_cost excludes the metric."""
    if metric in HIGHER_BETTER:
        num, den = floor - cand, floor - orig
    else:
        num, den = cand - floor, orig - floor
    if den <= 0:
        return None
    return num / den


def metric_costs(metrics, baseline):
    """Per-metric normalized cost (None where the case gives no signal). Reused by
    the bake-off so Method A is computed in exactly one place."""
    orig, floor = baseline["original"], baseline["reference_floor"]
    return {m: _cost(m, metrics[m], orig[m], floor[m]) for m in WEIGHTS}


def weighted_cost(costs):
    """Weighted mean of the per-metric costs -> Method A score (lower is better)."""
    num = den = 0.0
    for m, c in costs.items():
        if c is None or WEIGHTS[m] == 0:
            continue
        num += WEIGHTS[m] * c
        den += WEIGHTS[m]
    return round(num / den, 4) if den else None


# --- The simpler-but-worse guard --------------------------------------------
#
# Known soft spot of the whole project: low numbers can be gamed. Layer 2 already
# blocks anything that DELETES logic (behavior would change). What is left:
#   suspiciously-simple : correct but golfed below the clean reference -> FLAG only.
#   fragmentation-smell : per-function complexity at/below floor while the TOTALS
#                         are above it -> logic spread across many trivial functions.
# Both are FLAGS, not rejections: behavior is proven, and we have no objective
# (LLM-free) readability oracle, so rejecting a genuinely-simpler correct candidate
# would violate "objective only" and could throw away a better answer.
def guard_flags(metrics, floor):
    flags = []
    if (
        metrics["logical_loc"] < floor["logical_loc"]
        or metrics["cyclomatic_total"] < floor["cyclomatic_total"]
    ):
        flags.append("suspiciously-simple")
    if (
        metrics["cyclomatic_total"] > floor["cyclomatic_total"]
        and metrics["cyclomatic_max"] < floor["cyclomatic_max"]
        and metrics["logical_loc"] > floor["logical_loc"]
    ):
        flags.append("fragmentation-smell")
    return flags


@dataclass
class Evaluation:
    verdict: str  # "scored" | "rejected"
    reason_code: str | None  # taxonomy code if rejected; None if scored
    gate: str | None  # "tests" / "golden" if rejected; None if scored
    metrics: dict | None  # full freeze() basket; None if rejected
    weighted_cost: float | None  # Method A score (0=floor,1=original); None if rejected
    metric_costs: dict | None  # per-metric normalized cost; None if rejected
    flags: list = field(default_factory=list)  # guard flags
    feedback: str = ""  # human-readable, specific (Phase 3 feeds this back)


def evaluate(candidate_path, case_dir, timeout=10.0):
    case_dir = Path(case_dir)
    baseline = runinput.load_json(
        case_dir / "baseline_metrics.json", "baseline_metrics.json"
    )

    # Layers 1 & 2 (delegated to the existing gatekeeper; the sandbox runs there).
    v = classify(
        candidate_path,
        str(case_dir / "test_suite.py"),
        str(case_dir / "golden_io.json"),
        timeout,
    )
    if not v.ok:
        return Evaluation(
            "rejected", v.code, v.gate, None, None, None, feedback=_reject_feedback(v)
        )

    # Layer 3 (only reached when both gates pass).
    metrics = freeze(candidate_path)
    costs = metric_costs(metrics, baseline)
    cost = weighted_cost(costs)
    flags = guard_flags(metrics, baseline["reference_floor"])
    return Evaluation(
        "scored",
        None,
        None,
        metrics,
        cost,
        costs,
        flags,
        _score_feedback(metrics, baseline, cost, costs, flags),
    )


def _reject_feedback(v):
    detail = v.reason.strip()
    if len(detail) > 1500:  # keep pytest dumps usable as feedback
        detail = "...\n" + detail[-1500:]
    return (
        f"REJECTED at the {v.gate} gate (reason: {v.code}). Not scored: a "
        f"candidate that is not correct-and-behavior-identical is not a valid "
        f"answer, regardless of how simple it looks.\n" + detail
    )


def _score_feedback(metrics, baseline, cost, costs, flags):
    floor = baseline["reference_floor"]
    out = [
        f"PASSED the correctness and behavior gates. Weighted complexity cost "
        f"{cost} (0.0 = clean reference floor, 1.0 = bloated original; lower is better)."
    ]

    # Name the metrics still furthest from the floor, by weighted contribution.
    ranked = sorted(
        (
            (m, c)
            for m, c in costs.items()
            if c is not None and WEIGHTS[m] > 0 and c > 0.05
        ),
        key=lambda kv: WEIGHTS[kv[0]] * kv[1],
        reverse=True,
    )
    if ranked:
        # Direction-neutral wording: on some cases an axis is "perverse" (the bloated
        # original sits below the clean floor, e.g. merge_intervals cyclomatic_max,
        # where fragmentation lowered per-function max), so we show value+floor+cost
        # rather than claiming "above".
        gaps = "; ".join(
            f"{m}={metrics[m]} (floor {floor[m]}, cost {round(c, 2)})"
            for m, c in ranked[:3]
        )
        out.append(
            f"Largest weighted gaps from the reference floor: {gaps}. "
            f"Biggest contributor: {ranked[0][0]}."
        )
    else:
        out.append(
            "Every weighted metric is at or below the reference floor — near-optimal."
        )

    # Concrete, basket-grounded structural hints (no fabricated code locations).
    if metrics["dependency_count"] > floor["dependency_count"]:
        out.append(
            f"Unnecessary dependencies remain: {metrics['dependencies']} "
            f"({metrics['dependency_count']} vs floor {floor['dependency_count']})."
        )
    if metrics["dead_code_count"] > floor["dead_code_count"]:
        out.append(
            f"Dead code remains: {metrics['dead_code_count']} item(s) flagged "
            f"(floor {floor['dead_code_count']})."
        )
    if metrics["max_nesting_depth"] > floor["max_nesting_depth"]:
        out.append(
            f"Deepest nesting is {metrics['max_nesting_depth']} levels "
            f"(floor {floor['max_nesting_depth']})."
        )
    if "suspiciously-simple" in flags:
        out.append(
            "FLAG suspiciously-simple: metrics fall below the clean reference "
            "floor. Behavior is verified, so logic is intact, but this may be "
            "hard-to-read golfing — flagged for review, not rejected."
        )
    if "fragmentation-smell" in flags:
        out.append(
            "FLAG fragmentation-smell: per-function complexity is below the "
            "floor while total complexity and line count are above it — logic may "
            "be split across many trivial functions. Scored on totals, not rewarded."
        )
    return "\n".join(out)


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: python evaluator.py <candidate.py> <case_dir>")
    logsetup.configure()  # entry point: wire logging once (never at import)
    e = evaluate(sys.argv[1], sys.argv[2])
    result = {
        "verdict": e.verdict,
        "reason_code": e.reason_code,
        "gate": e.gate,
        "weighted_cost": e.weighted_cost,
        "flags": e.flags,
        "metrics": e.metrics,
    }
    log.info(
        json.dumps(result, indent=2),
        extra={
            "verdict": e.verdict,
            "reason_code": e.reason_code,
            "gate": e.gate,
            "weighted_cost": e.weighted_cost,
            "flags": e.flags,
        },
    )
    log.info("\nFEEDBACK:\n%s", e.feedback)


if __name__ == "__main__":
    main()
