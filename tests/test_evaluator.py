"""Regression tests for the single-file evaluator's Method A scoring (evaluator.py),
pinning the inverted-span defect in _cost.

DEFECT: _cost normalized every metric as a span from the original (cost 1.0) to the
reference floor (cost 0.0), guarding only den == 0. When the original is already
strictly BETTER than the floor on a metric, the improvement span is INVERTED
(den < 0) and the sign flips: a candidate worse than both the original and the floor
scored FAR BELOW the floor. Real instance (task_scheduler gen-2, see numbers below):
cyclomatic_max original 5, floor 6, candidate 11 scored -5.0 on that metric (weight
0.5), dragging the candidate's weighted cost to -0.3006 and steering the loop to
"fix" the wrong axis.

FIX: _cost returns None (no signal) whenever the original is NOT strictly worse than
the floor, that is whenever den <= 0, for both the higher-is-better and
lower-is-better branches. weighted_cost already excludes None metrics.

These tests FAIL on the pre-fix code and PASS after. Run from tools/:
    python -m pytest test_evaluator.py -q -p no:cacheprovider
"""

import pytest

from darwin.evaluator import _cost, metric_costs, weighted_cost

# Real task_scheduler aggregates. original/reference from
# mcases/task_scheduler/baseline_metrics.json; the candidate is the actual gen-2
# "best" recorded in reports/maggregate.json (cyclomatic_max 11). maintainability_index
# and source_loc carry weight 0 (informational), so their values do not affect the
# score; they are present only so metric_costs can iterate every WEIGHTS key.
TS_ORIGINAL = {
    "cyclomatic_total": 150,
    "logical_loc": 284,
    "maintainability_index": 43.0,
    "max_nesting_depth": 4,
    "dependency_count": 1,
    "dead_code_count": 12,
    "cyclomatic_max": 5,
    "source_loc": 295,
}
TS_FLOOR = {
    "cyclomatic_total": 63,
    "logical_loc": 100,
    "maintainability_index": 60.2,
    "max_nesting_depth": 4,
    "dependency_count": 0,
    "dead_code_count": 8,
    "cyclomatic_max": 6,
    "source_loc": 108,
}
TS_GEN2 = {
    "cyclomatic_total": 72,
    "logical_loc": 94,
    "maintainability_index": 55.0,
    "max_nesting_depth": 4,
    "dependency_count": 0,
    "dead_code_count": 8,
    "cyclomatic_max": 11,
    "source_loc": 100,
}
TS_BASELINE = {"original": TS_ORIGINAL, "reference_floor": TS_FLOOR}


def test_cost_inverted_span_lower_is_better_returns_none():
    """The exact failing case: lower-is-better cyclomatic_max, original 5 already
    BELOW floor 6 (inverted span), candidate 11 worse than both. Pre-fix returns
    -5.0; the fix returns None (no signal)."""
    assert _cost("cyclomatic_max", 11, 5, 6) is None


def test_cost_inverted_span_higher_is_better_returns_none():
    """Higher-is-better (maintainability_index) inverted span: original 70 already
    ABOVE floor 60, candidate 40 worse than both. Pre-fix returns -2.0; the fix
    returns None."""
    assert _cost("maintainability_index", 40, 70, 60) is None


def test_cost_degenerate_span_returns_none():
    """Pins existing behavior: original == floor leaves no span, so there is nothing
    to improve and we must not divide by zero. None before and after the fix."""
    assert _cost("cyclomatic_max", 7, 4, 4) is None


def test_cost_normal_span_returns_correct_finite_value():
    """Sanity, unchanged by the fix: a normal span (original strictly worse than the
    floor) still returns the linear interpolation, 0.0 at the floor and 1.0 at the
    original."""
    # lower-is-better: cyclomatic_total 72, original 150, floor 63.
    assert _cost("cyclomatic_total", 72, 150, 63) == pytest.approx(9 / 87)
    # both anchors land on their fixed costs.
    assert _cost("cyclomatic_total", 63, 150, 63) == pytest.approx(0.0)  # floor
    assert _cost("cyclomatic_total", 150, 150, 63) == pytest.approx(1.0)  # original
    # higher-is-better normal span: floor 80 above original 40, candidate 60.
    assert _cost("maintainability_index", 60, 40, 80) == pytest.approx(0.5)


def test_weighted_cost_excludes_none_metric():
    """weighted_cost drops a None metric entirely (no signal), weighting only the
    metrics that remain."""
    costs = {"cyclomatic_total": 0.2, "logical_loc": None, "cyclomatic_max": None}
    # Only cyclomatic_total survives, so the weighted mean is its own cost.
    assert weighted_cost(costs) == pytest.approx(0.2)


def test_task_scheduler_gen2_no_longer_scores_below_floor():
    """End-to-end: the real task_scheduler gen-2 candidate (cyclomatic_max 11, the
    rest as recorded) scored -0.3006 pre-fix, below the reference floor, because the
    inverted cyclomatic_max span contributed -5.0. With the fix that metric carries
    no signal (None) and is excluded, so the candidate scores AT OR ABOVE 0.0."""
    costs = metric_costs(TS_GEN2, TS_BASELINE)
    # The inverted span (original 5 below floor 6) now yields no signal.
    assert costs["cyclomatic_max"] is None
    # And the degenerate max_nesting_depth span (4 == 4) likewise yields none.
    assert costs["max_nesting_depth"] is None
    score = weighted_cost(costs)
    assert score >= 0.0, f"candidate still scores below floor: {score}"


def test_score_invariants_preserved():
    """THE BAR: the original anchors 1.0 and the reference floor anchors 0.0 on this
    case, regardless of which metrics the inverted/degenerate spans exclude."""
    assert weighted_cost(metric_costs(TS_ORIGINAL, TS_BASELINE)) == pytest.approx(1.0)
    assert weighted_cost(metric_costs(TS_FLOOR, TS_BASELINE)) == pytest.approx(0.0)
