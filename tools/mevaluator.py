"""The multi-file evaluator (v3 / V1). Scores ONE candidate multi-file unit
against ONE mcase, objectively, with no LLM anywhere. The single-function
evaluator's three-layer contract (tools/evaluator.py), lifted to the multi-file
domain, in the same strict order of authority:

  Layer 1  Correctness gate   — does the case test suite pass INSIDE the v2.0
                                container? (hard, blocking)
  Layer 2  Equivalence gate    — is the candidate differentially equivalent to
                                the original at the public API, with the
                                candidate inside the container? (blocking)
  Layer 3  Complexity score    — only for candidates that cleared 1 and 2.

Layer 1 reuses the verify_case container-pytest pattern (the candidate is
untrusted, so its test suite runs in the locked-down container, never imported
here). Layer 2 reuses tools/mverify.py exactly as built in V1 Prompt 1 (the
candidate replays inside the container; the original replays host-side; the
comparison stays host-side). Layer 3 reuses tools/mcase_metrics.py for the
multi-file metric basket and the v1 structural scoring (WEIGHTS, _cost,
weighted_cost, guard_flags from evaluator.py; maintainability index excluded,
see decision 0004) against the case reference floor. A candidate that fails a
gate is NOT scored — a broken answer is not a valid answer, however clean it
looks. Layer 3 can never promote a candidate past a gate.

CONCURRENCY SAFETY (decision 0024). The evaluator's loading state is now safe
under concurrent use. Every dynamic import on the equivalence path mints its
sys.modules name from a uuid, not a module-global counter (so no non-atomic
read-modify-write on shared state): the candidate corpus (mverify._load_corpus),
the host-side original unit replayed via mdiffer.load_unit, and the mcase aux
module (validate_mcase._load_module). The container path is likewise safe by
construction -- sandbox_container gives each run a uuid-unique container name and
a fresh tempfile working directory, so two concurrent container evaluations can
collide on neither a name nor a directory. Production evaluation nonetheless still
runs SEQUENTIALLY, one candidate per call; parallel candidate evaluation is not
activated here and remains a later phase. This phase makes the state safe to
parallelize, it does not parallelize it.

Usage: python mevaluator.py <case_dir> <candidate_unit_dir>
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import logsetup
import runinput
import sandbox_container as sandbox
from evaluator import WEIGHTS, _cost, guard_flags, weighted_cost
from mcase_metrics import unit_metrics
from mverify import _unit_files, check_equivalence_containerized
from oracle_markers import CANDIDATE_OUTCOME_PREFIX, ORIGINAL_OUTCOME_PREFIX
from verify_case import TESTS_FAILED, _classify_run, _LABEL

log = logsetup.get_logger(
    "mevaluator"
)  # operational log -> stderr (configured at the entry point)

NON_EQUIVALENT = "non-equivalent"  # the equivalence gate's rejection code


@dataclass
class MEvaluation:
    verdict: str  # "scored" | "rejected"
    reason_code: str | None  # taxonomy code if rejected; None if scored
    gate: str | None  # "tests" / "equivalence" if rejected; None if scored
    metrics: (
        dict | None
    )  # unit_metrics() basket (aggregate + per_file); None if rejected
    weighted_cost: float | None  # Method A score (0=floor,1=original); None if rejected
    metric_costs: dict | None  # per-metric normalized cost; None if rejected
    flags: list = field(default_factory=list)  # guard flags
    feedback: str = ""  # human-readable, specific (V2 loop feeds this back)

    # The verdict-emission boundary payload (decision 0032). to_dict / from_dict are
    # the single serialization of a verdict: lossless and JSON-ready, so a 2.0
    # out-of-process emitter can hand the same MEvaluation back across a process
    # boundary. The in-process default never needs them; they exist so the boundary
    # exists. There is one serialization, used by main() and (in 2.0) the boundary.
    def to_dict(self):
        """Serialize this verdict losslessly to a JSON-ready dict. Every field is
        included -- the None-valued ones of a rejected verdict among them -- so
        from_dict() reconstructs an identical MEvaluation. metrics / metric_costs are
        plain dicts and flags is a list, so the result is directly json.dumps-able."""
        return {
            "verdict": self.verdict,
            "reason_code": self.reason_code,
            "gate": self.gate,
            "metrics": self.metrics,
            "weighted_cost": self.weighted_cost,
            "metric_costs": self.metric_costs,
            "flags": self.flags,
            "feedback": self.feedback,
        }

    @classmethod
    def from_dict(cls, data):
        """Reconstruct an MEvaluation from to_dict()'s output: the exact inverse,
        lossless for both the scored and the rejected shape (including the None
        fields). The dict keys are the field names, so this is the boundary decode."""
        return cls(
            verdict=data["verdict"],
            reason_code=data["reason_code"],
            gate=data["gate"],
            metrics=data["metrics"],
            weighted_cost=data["weighted_cost"],
            metric_costs=data["metric_costs"],
            flags=data["flags"],
            feedback=data["feedback"],
        )


def _correctness_gate(case_dir, candidate_dir, timeout):
    """Layer 1: run the case test suite inside the container against the
    candidate unit. Reuses the verify_case container-pytest pattern. The
    candidate unit goes in under candidate/; the suite selects it through
    MCASE_UNIT=candidate (set with `env`, since sandbox_container.run takes no
    env). mdiffer.py rides along because test_suite.py imports load_unit from
    it. Returns (ok, code, reason)."""
    files = {
        **_unit_files(candidate_dir),
        "test_suite.py": (Path(case_dir) / "test_suite.py").read_text(encoding="utf-8"),
        "mdiffer.py": (Path(__file__).parent / "mdiffer.py").read_text(
            encoding="utf-8"
        ),
    }
    res = sandbox.run(
        files,
        [
            "env",
            "MCASE_UNIT=candidate",
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "test_suite.py",
        ],
        timeout,
    )
    if res.status == sandbox.OK:
        return True, None, "test suite passed inside the container"
    code = _classify_run(res, TESTS_FAILED)
    detail = res.stdout + res.stderr
    return False, code, f"pytest: {_LABEL[code]}:\n" + detail


def evaluate(case_dir, candidate_dir, timeout=30.0):
    case_dir = Path(case_dir)
    baseline = runinput.load_json(
        case_dir / "baseline_metrics.json", "baseline_metrics.json"
    )

    # Layer 1 (correctness): the candidate's test suite must pass in the container.
    ok, code, reason = _correctness_gate(case_dir, candidate_dir, timeout)
    if not ok:
        return MEvaluation(
            "rejected",
            code,
            "tests",
            None,
            None,
            None,
            feedback=_reject_tests_feedback(code, reason),
        )

    # Layer 2 (equivalence): only reached after correctness passes. mverify runs
    # the candidate in the container; original and comparison stay host-side.
    eq, witness, stats = check_equivalence_containerized(
        case_dir, candidate_dir, timeout
    )
    if not eq:
        return MEvaluation(
            "rejected",
            NON_EQUIVALENT,
            "equivalence",
            None,
            None,
            None,
            feedback=_reject_equivalence_feedback(witness, stats),
        )

    # Layer 3 (complexity): only reached when both gates pass.
    metrics = unit_metrics(candidate_dir)
    cand_agg = metrics["aggregate"]
    orig_agg = baseline["original"]["aggregate"]
    floor_agg = baseline["reference"]["aggregate"]
    costs = _metric_costs(cand_agg, orig_agg, floor_agg)
    cost = weighted_cost(costs)
    flags = guard_flags(cand_agg, floor_agg)
    return MEvaluation(
        "scored",
        None,
        None,
        metrics,
        cost,
        costs,
        flags,
        _score_feedback(metrics, floor_agg, cost, costs, flags),
    )


def _metric_costs(cand_agg, orig_agg, floor_agg):
    """Per-metric normalized cost over the multi-file aggregate, reusing the v1
    _cost (0.0 at the reference floor, 1.0 at the original). maintainability_index
    is in WEIGHTS but not in the aggregate (mcase_metrics keeps it per-file only;
    weight 0 anyway, decision 0004), so it is skipped rather than fabricated."""
    return {
        m: _cost(m, cand_agg[m], orig_agg[m], floor_agg[m])
        for m in WEIGHTS
        if m in cand_agg
    }


# ---------------------------------------------------------------- feedback


def _reject_tests_feedback(code, reason):
    detail = reason.strip()
    if len(detail) > 1500:  # keep pytest dumps usable as feedback
        detail = "...\n" + detail[-1500:]
    return (
        f"REJECTED at the correctness gate (reason: {code}). Not scored: a "
        f"candidate whose test suite does not pass inside the container is not "
        f"a valid answer, regardless of how simple it looks.\n" + detail
    )


def _reject_equivalence_feedback(witness, stats):
    head = (
        f"REJECTED at the equivalence gate (reason: {NON_EQUIVALENT}). Not "
        f"scored: the candidate is not behavior-identical to the original at "
        f"the public API over the sequence corpus."
    )
    if witness is not None:
        # The two outcome lines carry the oracle; mloop strips them by the shared
        # prefixes (decision 0025), so the producer must emit them with those prefixes.
        return (
            head + f"\nFirst diverging sequence: {witness['sequence']}, "
            f"call #{witness['call_index']} ({witness['call']}).\n"
            f"  {ORIGINAL_OUTCOME_PREFIX} {witness['original']}\n"
            f"  {CANDIDATE_OUTCOME_PREFIX} {witness['candidate']}"
        )
    # Fail-closed (no per-call witness): mverify could not obtain a verifiable
    # candidate replay (import error, missing method, or an over-cap/unparseable
    # result frame). It rejects to NOT EQUIVALENT by design (carried flag 1).
    return (
        head
        + f"\nFailed closed (no verifiable replay): {stats.get('error', 'unknown')}"
    )


def _score_feedback(metrics, floor, cost, costs, flags):
    agg = metrics["aggregate"]
    out = [
        f"PASSED the correctness and equivalence gates. Weighted complexity cost "
        f"{cost} (0.0 = clean reference floor, 1.0 = bloated original; lower is better)."
    ]

    # Name the metrics still furthest from the floor, by weighted contribution,
    # and for each name the candidate file(s) carrying the most of that metric.
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
        parts = []
        for m, c in ranked[:3]:
            parts.append(
                f"{m}={agg[m]} (floor {floor[m]}, cost {round(c, 2)}) "
                f"in {_top_files(metrics, m)}"
            )
        out.append(
            "Largest weighted gaps from the reference floor: "
            + "; ".join(parts)
            + f". Biggest contributor: {ranked[0][0]}."
        )
    else:
        out.append(
            "Every weighted metric is at or below the reference floor — near-optimal."
        )

    # Concrete, basket-grounded structural hints (no fabricated code locations).
    if agg["dependency_count"] > floor["dependency_count"]:
        out.append(
            f"Unnecessary dependencies remain across the unit: "
            f"{agg['dependencies']} ({agg['dependency_count']} vs floor "
            f"{floor['dependency_count']})."
        )
    if agg["dead_code_count"] > floor["dead_code_count"]:
        out.append(
            f"Dead code remains: {agg['dead_code_count']} item(s) flagged "
            f"across the unit (floor {floor['dead_code_count']})."
        )
    if agg["max_nesting_depth"] > floor["max_nesting_depth"]:
        out.append(
            f"Deepest nesting is {agg['max_nesting_depth']} levels "
            f"(floor {floor['max_nesting_depth']}), in "
            f"{_top_files(metrics, 'max_nesting_depth')}."
        )
    if agg["file_count"] > floor["file_count"]:
        out.append(
            f"The unit spans {agg['file_count']} files (reference uses "
            f"{floor['file_count']}); structure may be over-split."
        )
    if "suspiciously-simple" in flags:
        out.append(
            "FLAG suspiciously-simple: aggregate metrics fall below the clean "
            "reference floor. Behavior is verified, so logic is intact, but this "
            "may be hard-to-read golfing — flagged for review, not rejected."
        )
    if "fragmentation-smell" in flags:
        out.append(
            "FLAG fragmentation-smell: per-function complexity is below the floor "
            "while total complexity and line count are above it — logic may be "
            "split across many trivial functions. Scored on totals, not rewarded."
        )
    return "\n".join(out)


def _top_files(metrics, metric):
    """The candidate file(s) carrying the most of `metric`, from the per_file
    basket. For the maxed metrics (cyclomatic_max, max_nesting_depth) this is the
    file(s) at the unit max; for the summed metrics it is the largest contributor.
    Used so the feedback points at WHERE the remaining complexity lives."""
    per_file = {
        name: pf
        for name, pf in metrics["per_file"].items()
        if metric in pf and pf[metric] > 0
    }
    if not per_file:
        return "no single file"
    top = max(per_file.values(), key=lambda pf: pf[metric])[metric]
    names = [name for name, pf in per_file.items() if pf[metric] == top]
    return ", ".join(f"{name} ({top})" for name in sorted(names))


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: python mevaluator.py <case_dir> <candidate_unit_dir>")
    logsetup.configure()  # entry point: wire logging once (never at import)
    e = evaluate(sys.argv[1], sys.argv[2])
    # One serialization, used in one place (decision 0032): the SAME to_dict() that
    # is the verdict-emission boundary payload, rather than an ad-hoc dict, so the
    # boundary shape is exercised here and there is a single source of it.
    result = e.to_dict()
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
