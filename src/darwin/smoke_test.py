"""End-to-end smoke test: the first genuine run of the assembled Phase 0/1/2 stack on
HONEST input. No LLM, no generation, no loop — an integration check.

For each seed case it evaluates two REAL artifacts as candidates, through the real
evaluator (real sandbox, real golden replay, real metrics):
  - reference.py : known-correct AND simpler than original (the clean target)
  - original.py  : known-correct but bloated (the control)
and confirms the stack performs the task: both pass the gates, and the clean
reference scores BETTER (lower weighted cost) than the bloated original.

Exit 0 = the stack works on honest input; exit 1 = a real integration bug.
Usage: python smoke_test.py
"""

import sys

from darwin import paths
from darwin.evaluator import evaluate

# The cases directory resolves LAZILY, never at import: the module must import cleanly
# without a checkout on disk (the P8.3 audit found import-time resolution broke that).
# It resolves at first access (inside _seed_cases via main), not at import; raises
# RuntimeError via paths.data_root() when no data root is locatable.
_THIS = sys.modules[__name__]


def __getattr__(name):
    if name == "CASES":
        return paths.cases_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


COLS = [
    "cyclomatic_total",
    "cyclomatic_max",
    "logical_loc",
    "source_loc",
    "dependency_count",
    "dead_code_count",
    "max_nesting_depth",
    "maintainability_index",
]


def _seed_cases():
    for d in sorted(_THIS.CASES.iterdir()):
        if (d / "reference.py").exists() and (d / "original.py").exists():
            yield d


def run_case(case_dir):
    # reaching verdict == "scored" means BOTH gates passed (the evaluator only scores
    # candidates that clear Layer 1 correctness and Layer 2 behavior).
    ref = evaluate(str(case_dir / "reference.py"), case_dir)
    orig = evaluate(str(case_dir / "original.py"), case_dir)

    print("=" * 78)
    print(f"CASE: {case_dir.name}")
    print("=" * 78)
    print(
        f"  reference (clean)  : verdict={ref.verdict:<8} weighted_cost={ref.weighted_cost}"
    )
    print(
        f"  original  (bloated): verdict={orig.verdict:<8} weighted_cost={orig.weighted_cost}"
    )

    print(f"\n  {'metric':<24}{'reference':>12}{'original':>12}")
    for m in COLS:
        rv = ref.metrics[m] if ref.metrics else "-"
        ov = orig.metrics[m] if orig.metrics else "-"
        print(f"  {m:<24}{str(rv):>12}{str(ov):>12}")

    if ref.feedback:
        print("\n  reference feedback:\n    " + ref.feedback.replace("\n", "\n    "))

    msgs, ok = [], True
    if ref.verdict != "scored":
        ok = False
        msgs.append(f"BUG: reference did NOT pass the gates (reason={ref.reason_code})")
    if orig.verdict != "scored":
        ok = False
        msgs.append(f"BUG: original did NOT pass the gates (reason={orig.reason_code})")
    if ref.verdict == "scored" and orig.verdict == "scored":
        if ref.weighted_cost < orig.weighted_cost:
            msgs.append(
                f"OK: clean reference {ref.weighted_cost} < bloated original "
                f"{orig.weighted_cost} (sensible ordering on real input)"
            )
        else:
            ok = False
            msgs.append(
                f"BUG: reference cost {ref.weighted_cost} is NOT better than "
                f"original {orig.weighted_cost}"
            )
    print("\n  RESULT: " + "; ".join(msgs) + "\n")
    return ok


def main():
    results = [run_case(c) for c in _seed_cases()]
    print("=" * 78)
    if results and all(results):
        print(
            f"SMOKE TEST PASSED: {len(results)} case(s). The Phase 0/1/2 stack runs the "
            "real task end to end: clean reference passes both gates and beats the "
            "bloated original on every case."
        )
        sys.exit(0)
    print("SMOKE TEST FAILED: integration bug (see BUG line(s) above).")
    sys.exit(1)


if __name__ == "__main__":
    main()
