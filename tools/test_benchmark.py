"""Offline tests for the single-file benchmark aggregate builder (benchmark.aggregate).

No API key and no Docker: every test drives the real aggregate() with synthetic
summarize_run-shaped rows. The focus here is the feedback_load_bearing materiality
semantics (decision 0021): the field is true only when some needed-feedback case's
later-generation gain strictly exceeds FEEDBACK_MATERIALITY_EPSILON_PP, not merely
when a case used a later generation at all.

  cd tools && python -m pytest test_benchmark.py -q -p no:cacheprovider
"""

import benchmark
from feedback_materiality import FEEDBACK_MATERIALITY_EPSILON_PP as EPS


def _fake_summary(
    case,
    *,
    improved,
    best_gen,
    first_scored=1,
    first_pass=99.5,
    bloat=99.8,
    gain=None,
    category="verbose_patterns",
    difficulty="hard",
    cost=0.03,
    tin=1000,
    tout=500,
    wc=0.0,
):
    """A summarize_run-shaped row carrying every field benchmark.aggregate() reads."""
    return {
        "case": case,
        "category": category,
        "difficulty": difficulty,
        "verdict": (
            "improved (best candidate returned)"
            if improved
            else "no improvement (baseline original returned)"
        ),
        "improved_over_baseline": improved,
        "best_weighted_cost": wc,
        "bloat_removed_pct": bloat,
        "first_pass_bloat_removed_pct": first_pass,
        "feedback_gain_pp": gain,
        "generations_attempted": best_gen if best_gen else 1,
        "best_generation": best_gen,
        "first_scored_generation": first_scored,
        "floor_reached": True,
        "total_cost_usd": cost,
        "total_input_tokens": tin,
        "total_output_tokens": tout,
        "best_flags": [],
        "halted": None,
        "structural_changes_from_first": [],
        "per_metric": [],
        "run_dir": f"/runs/{case}",
    }


def test_feedback_load_bearing_false_when_all_gains_within_noise():
    """needed-feedback cases whose gains are at or below the materiality floor do
    NOT make feedback_load_bearing true; the cases still appear in the list. This is
    the real committed single-file shape: two gen-2 bests, gains 0.37 and 0.40 pp."""
    rows = [
        _fake_summary("format_duration", improved=True, best_gen=2, gain=0.37),
        _fake_summary("int_to_words", improved=True, best_gen=2, gain=0.40),
    ]
    agg = benchmark.aggregate(rows, "test-model", 5, 2)

    # The factual record of which cases used a later generation is unchanged.
    assert len(agg["needed_feedback_cases"]) == 2
    assert {c["case"] for c in agg["needed_feedback_cases"]} == {
        "format_duration",
        "int_to_words",
    }
    # But the gains are within run-to-run noise, so the loop is NOT load-bearing.
    assert agg["feedback_load_bearing"] is False


def test_feedback_load_bearing_false_at_the_floor():
    """A gain exactly at the floor does not qualify: the comparison is strictly >."""
    rows = [_fake_summary("at_floor", improved=True, best_gen=2, gain=EPS)]
    agg = benchmark.aggregate(rows, "test-model", 5, 2)
    assert len(agg["needed_feedback_cases"]) == 1
    assert agg["feedback_load_bearing"] is False


def test_feedback_load_bearing_true_when_a_gain_exceeds_floor():
    """A single needed-feedback case whose gain exceeds the materiality floor makes
    feedback_load_bearing true, even alongside sub-floor cases."""
    rows = [
        _fake_summary("below", improved=True, best_gen=2, gain=0.37),
        _fake_summary("material", improved=True, best_gen=2, gain=EPS + 0.01),
    ]
    agg = benchmark.aggregate(rows, "test-model", 5, 2)
    assert len(agg["needed_feedback_cases"]) == 2
    assert agg["feedback_load_bearing"] is True
