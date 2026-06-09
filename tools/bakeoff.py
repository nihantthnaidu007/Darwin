"""The Layer-3 scoring bake-off: implement BOTH scoring methods and compare them
on ground truth (hand-built candidates over the two seed cases), so the choice is
made by how each method actually ranks real candidates, not by opinion.

  Method A  Weighted sum   — evaluator.weighted_cost (absolute, per-candidate).
  Method B  Pareto dominance — partial order over the metric basket, with a
                              documented tiebreak. Set-relative, defined HERE.

It also runs a deliberately naive "cyclomatic_max only" ranker to show the
fragmentation trap is real, and that A and B both avoid it.

Every candidate is run through the REAL evaluator (real Layers 1+2 gates via the
sandbox, real Layer-3 metrics), so the rankings are over candidates that genuinely
pass correctness and behavior. Run: python bakeoff.py
"""
import tempfile
from pathlib import Path

from evaluator import HIGHER_BETTER, evaluate

CASES = Path(__file__).resolve().parent.parent / "cases"

# Pareto basket: the meaningful STRUCTURAL metrics. source_loc is dropped (near-duplicate
# of logical_loc — would double-count size in the dominance test). maintainability_index
# is dropped too: the audit showed it is cosmetic-gameable at single-function scale (a
# docstring/rename raises MI with no real simplification), so it must not drive dominance
# or the tiebreak — consistent with Method A weighting it 0. MI stays in the display table
# below as informational only.
PARETO_METRICS = [
    "cyclomatic_total", "cyclomatic_max",
    "logical_loc", "dependency_count", "dead_code_count", "max_nesting_depth",
]

# ---------------------------------------------------------------------------
# The hand-built candidate sets. Per case:
#   clean              (1) near-optimal — we use the case's own reference.py
#   middling-*         (2) partially simplified
#   original           (3) the bloated control — the case's own original.py
#   fragmented         (6) correct + behavior-matching, logic exploded into tiny fns
#   broken             (4) a test fails           -> must be rejected at Layer 1
#   behavior-mismatch  (5) passes tests, fails golden -> must be rejected at Layer 2
# "kind" is "file" (path, reused real artifact) or "src" (inline source).
# "expect" is the verdict we assert: "scored" or "rejected".

SUM_EVENS = [
    ("clean", "file", "sum_evens/reference.py", "scored"),
    ("middling-loop", "src", '''\
def sum_evens(numbers):
    total = 0
    for n in numbers:
        if n % 2 == 0:
            total += n
    return total
''', "scored"),
    ("middling-helper+dep", "src", '''\
import functools


def _is_even(n):
    return n % 2 == 0


def sum_evens(numbers):
    evens = [n for n in numbers if _is_even(n)]
    return functools.reduce(lambda a, b: a + b, evens, 0)
''', "scored"),
    ("original (control)", "file", "sum_evens/original.py", "scored"),
    ("fragmented (trap)", "src", '''\
def _is_even(n):
    return n % 2 == 0


def _add(a, b):
    return a + b


def _accumulate(values):
    total = 0
    for v in values:
        total = _add(total, v)
    return total


def _select_evens(values):
    return [v for v in values if _is_even(v)]


def sum_evens(numbers):
    return _accumulate(_select_evens(numbers))
''', "scored"),
    ("broken (test fails)", "src", '''\
def sum_evens(numbers):
    return sum(numbers)
''', "rejected"),
    ("behavior-mismatch", "src", '''\
def sum_evens(numbers):
    numbers = list(numbers)
    # Deliberately narrows behavior on an input the suite never probes: no test
    # uses a length-20 list, but the golden I/O does ([1..20] -> 110). Passes
    # pytest, fails golden replay -> caught only by Layer 2.
    if len(numbers) == 20:
        return 0
    return sum(n for n in numbers if n % 2 == 0)
''', "rejected"),
]

MERGE_INTERVALS = [
    ("clean", "file", "merge_intervals/reference.py", "scored"),
    ("middling-overlap-helper", "src", '''\
def _overlaps(last, interval):
    return interval[0] <= last[1]


def merge_intervals(intervals):
    merged = []
    for interval in sorted(intervals):
        if merged and _overlaps(merged[-1], interval):
            merged[-1][1] = max(merged[-1][1], interval[1])
        else:
            merged.append([interval[0], interval[1]])
    return merged
''', "scored"),
    ("middling-sort+dep", "src", '''\
from operator import itemgetter


def _sort_intervals(intervals):
    return sorted(intervals, key=itemgetter(0, 1))


def merge_intervals(intervals):
    merged = []
    for start, end in _sort_intervals(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
''', "scored"),
    ("original (control)", "file", "merge_intervals/original.py", "scored"),
    ("fragmented (trap)", "src", '''\
def _start(iv):
    return iv[0]


def _end(iv):
    return iv[1]


def _sorted_intervals(intervals):
    return sorted(intervals)


def _touches(last, iv):
    return _start(iv) <= _end(last)


def _extend(last, iv):
    last[1] = max(_end(last), _end(iv))


def _fresh(iv):
    return [_start(iv), _end(iv)]


def _merge_one(merged, iv):
    if merged and _touches(merged[-1], iv):
        _extend(merged[-1], iv)
    else:
        merged.append(_fresh(iv))


def merge_intervals(intervals):
    merged = []
    for iv in _sorted_intervals(intervals):
        _merge_one(merged, iv)
    return merged
''', "scored"),
    ("broken (test fails)", "src", '''\
def merge_intervals(intervals):
    merged = []
    for start, end in intervals:  # forgot to sort -> unsorted input misbehaves
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
''', "rejected"),
]

# A deliberately golfed, correct, behavior-matching candidate: an unreadable nested
# ternary inside a reduce-lambda. It games the metrics BELOW the clean reference
# (negative weighted cost) — the residual gaming risk Layer 2 cannot catch (behavior
# is preserved). Demonstrated separately from the rankings precisely because it would
# rank #1 by raw cost; the suspiciously-simple FLAG is the mitigation.
GOLFED_MERGE = '''\
import functools


def merge_intervals(intervals):
    return functools.reduce(
        lambda m, iv: (m[:-1] + [[m[-1][0], max(m[-1][1], iv[1])]])
        if m and iv[0] <= m[-1][1] else m + [[iv[0], iv[1]]],
        sorted(intervals), [])
'''


def _evaluate_candidate(kind, payload, case_dir):
    if kind == "file":
        return evaluate(str(CASES / payload), case_dir)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_text(payload, encoding="utf-8")
        return evaluate(str(path), case_dir)


# --- Method B: Pareto dominance --------------------------------------------
def _oriented(metrics):
    """Re-orient so lower is better on every axis. HIGHER_BETTER members would be
    negated, but the basket is now all lower-better (MI was dropped from scoring)."""
    return {m: (-metrics[m] if m in HIGHER_BETTER else metrics[m]) for m in PARETO_METRICS}


def _dominates(a, b):
    """a dominates b: <= on every metric AND < on at least one (oriented dicts)."""
    return (all(a[m] <= b[m] for m in PARETO_METRICS)
            and any(a[m] < b[m] for m in PARETO_METRICS))


def _pareto_layers(scored):
    """Non-dominated sorting: front 0 = the Pareto-optimal set, remove, repeat.
    scored: list of (label, metrics). Returns list of layers (each a list of labels)."""
    remaining = [(lbl, _oriented(m)) for lbl, m in scored]
    layers = []
    while remaining:
        front = [(lbl, o) for lbl, o in remaining
                 if not any(_dominates(o2, o) for lbl2, o2 in remaining if lbl2 != lbl)]
        layers.append([lbl for lbl, _ in front])
        front_labels = {lbl for lbl, _ in front}
        remaining = [(lbl, o) for lbl, o in remaining if lbl not in front_labels]
    return layers


# Documented tiebreak for incomparable candidates (a small, explicit value judgment):
# total branching first, then total lines, then per-function max LAST. Deliberately
# anti-fragmentation: totals dominate the order. (maintainability_index was removed
# from the tiebreak too — cosmetic-gameable, see the PARETO_METRICS note.)
def _tiebreak(metrics):
    return (metrics["cyclomatic_total"], metrics["logical_loc"],
            metrics["cyclomatic_max"])


def _method_b_order(scored):
    by_label = dict(scored)
    order = []
    for layer in _pareto_layers(scored):
        order.extend(sorted(layer, key=lambda lbl: _tiebreak(by_label[lbl])))
    return order


# ---------------------------------------------------------------------------
_COLS = ["cyclomatic_total", "cyclomatic_max", "logical_loc", "dependency_count",
         "dead_code_count", "max_nesting_depth", "maintainability_index"]
_HDR = {"cyclomatic_total": "ccTot", "cyclomatic_max": "ccMax", "logical_loc": "lloc",
        "dependency_count": "deps", "dead_code_count": "dead",
        "max_nesting_depth": "nest", "maintainability_index": "MI"}


def _print_table(results):
    head = f"  {'candidate':<26}{'verdict':<10}{'cost':>6}  " + \
           "".join(f"{_HDR[c]:>7}" for c in _COLS) + "  flags/reason"
    print(head)
    print("  " + "-" * (len(head) - 2))
    for lbl, e in results:
        if e.verdict == "scored":
            cells = "".join(f"{e.metrics[c]:>7}" for c in _COLS)
            extra = ",".join(e.flags)
            cost = f"{e.weighted_cost:>6}"
        else:
            cells = "".join(f"{'-':>7}" for _ in _COLS)
            extra = f"{e.gate}:{e.reason_code}"
            cost = f"{'-':>6}"
        print(f"  {lbl:<26}{e.verdict:<10}{cost}  {cells}  {extra}")


def _ranking_line(name, order, costs=None):
    if costs:
        parts = [f"{i+1}. {lbl} ({costs[lbl]})" for i, lbl in enumerate(order)]
    else:
        parts = [f"{i+1}. {lbl}" for i, lbl in enumerate(order)]
    print(f"  {name}: " + "  ".join(parts))


def run_case(name, candidates):
    print("=" * 100)
    print(f"CASE: {name}")
    print("=" * 100)

    results = []
    for lbl, kind, payload, expect in candidates:
        e = _evaluate_candidate(kind, payload, CASES / name)
        results.append((lbl, e))
        assert e.verdict == expect, \
            f"{lbl}: expected {expect}, got {e.verdict} ({e.reason_code})"
    _print_table(results)

    scored = [(lbl, e.metrics) for lbl, e in results if e.verdict == "scored"]
    costs = {lbl: e.weighted_cost for lbl, e in results if e.verdict == "scored"}

    a_order = sorted(costs, key=lambda lbl: costs[lbl])
    b_order = _method_b_order(scored)
    naive_order = sorted(scored, key=lambda x: x[1]["cyclomatic_max"])
    naive_order = [lbl for lbl, _ in naive_order]

    print("\n  RANKINGS (best -> worst):")
    _ranking_line("Method A (weighted)", a_order, costs)
    _ranking_line("Method B (Pareto+tiebreak)", b_order)
    _ranking_line("NAIVE cyclomatic_max only", naive_order)

    print("\n  Pareto layers (front 0 = non-dominated):")
    for i, layer in enumerate(_pareto_layers(scored)):
        print(f"    layer {i}: {layer}")

    # Did each method put near-optimal first, original last, middling between?
    clean = "clean"
    orig = next(lbl for lbl in costs if lbl.startswith("original"))
    frag = next((lbl for lbl in costs if lbl.startswith("fragmented")), None)
    print("\n  SENSIBLE-ORDER CHECK:")
    for mname, order in [("A", a_order), ("B", b_order)]:
        best_ok = order[0] == clean
        worst_ok = order[-1] == orig
        print(f"    Method {mname}: near-optimal first? {best_ok} ({order[0]});  "
              f"original last? {worst_ok} ({order[-1]})")

    # Fragmentation trap: is the fragmented candidate ranked ABOVE clean?
    if frag:
        m = next(mt for lbl, mt in scored if lbl == clean)
        fmt = next(mt for lbl, mt in scored if lbl == frag)
        dom_cf = _dominates(_oriented(m), _oriented(fmt))
        dom_fc = _dominates(_oriented(fmt), _oriented(m))
        rel = ("clean dominates fragmented" if dom_cf else
               "fragmented dominates clean" if dom_fc else "INCOMPARABLE")
        print("\n  FRAGMENTATION-TRAP CHECK (does the method rank fragmented above clean?):")
        print(f"    metric facts: clean ccMax={m['cyclomatic_max']} ccTot={m['cyclomatic_total']} "
              f"lloc={m['logical_loc']}  |  fragmented ccMax={fmt['cyclomatic_max']} "
              f"ccTot={fmt['cyclomatic_total']} lloc={fmt['logical_loc']}")
        print(f"    Pareto relation clean vs fragmented: {rel}")
        for mname, order in [("A", a_order), ("B", b_order), ("NAIVE", naive_order)]:
            above = order.index(frag) < order.index(clean)
            verdict = "FOOLED (frag above clean)" if above else "ok (clean above frag)"
            print(f"    Method {mname}: {verdict}")
    print()
    return a_order, b_order, costs


def demo_suspiciously_simple():
    print("=" * 100)
    print("SUSPICIOUSLY-SIMPLE GUARD (deliberately golfed candidate, shown OUTSIDE the rankings)")
    print("=" * 100)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_text(GOLFED_MERGE, encoding="utf-8")
        e = evaluate(str(path), CASES / "merge_intervals")
    assert e.verdict == "scored", e.reason_code
    print(f"  golfed merge_intervals -> verdict={e.verdict}, weighted_cost={e.weighted_cost} "
          f"(NEGATIVE = scores 'better' than the clean floor), flags={e.flags}")
    print(f"  metrics: cyclomatic_total={e.metrics['cyclomatic_total']} "
          f"(floor 4), logical_loc={e.metrics['logical_loc']} (floor 8)")
    print("  -> It games the basket below the floor and would rank #1 by raw cost, beating")
    print("     'clean'. Behavior is verified (Layer 2), so logic is intact; the")
    print("     suspiciously-simple FLAG is what surfaces the unreadable golfing. Policy:")
    print("     FLAG for review, do NOT reject (no objective LLM-free readability oracle).")
    print()


def main():
    run_case("sum_evens", SUM_EVENS)
    run_case("merge_intervals", MERGE_INTERVALS)
    demo_suspiciously_simple()
    print("=" * 100)
    print("Note: merge_intervals has no 'behavior-mismatch' candidate. Its test suite's "
          "input set is a SUPERSET of its golden I/O inputs, so any candidate wrong on a "
          "golden input is also wrong on a test -> Layer 1 catches it first. The Layer-2 "
          "gate is therefore demonstrated on sum_evens (golden has a length-20 input the "
          "suite never probes).")
    print("See the final report for the A-vs-B recommendation.")


if __name__ == "__main__":
    main()
