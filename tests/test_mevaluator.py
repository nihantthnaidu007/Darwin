"""Tests for the multi-file evaluator (mevaluator.py).

Docker required (image darwin-sandbox:py313): the correctness gate runs the
case test suite inside the v2.0 container, and the equivalence gate replays the
candidate inside it. Run from the repo root:

    python -m pytest tests/test_mevaluator.py -v

Covers, per success criterion:
- each mcase's clean reference passes both gates and scores AT the floor (0.0);
- each mcase's bloated original passes both gates and scores WORSE (~1.0);
- a candidate whose test suite fails is rejected at correctness (tests-failed),
  with no score;
- a V0 planted break that passes the suite but the corpus catches is rejected at
  the equivalence gate (non-equivalent), with the first divergence in the feedback;
- the result shape mirrors the v1 evaluator contract;
- carried flag 1: an outcome-bloated candidate overflows mverify's 1 MB read-back
  cap and fails CLOSED to non-equivalent (not crashed, not falsely equivalent).
  Exercised at the equivalence-gate level because the full evaluator rejects such
  a candidate earlier, at correctness: the suite pins outcomes to small values, so
  an outcome-bloated unit cannot pass pytest and never reaches the cap.
"""

import json

import pytest

from darwin.mevaluator import NON_EQUIVALENT, evaluate
from darwin.mverify import check_equivalence_containerized
from darwin.validate_mcase import MCASES, _load_module, _materialize_break

CASES = sorted(p.name for p in MCASES.iterdir() if (p / "meta.json").exists())

# A break per case that PASSES the case test suite yet the corpus CATCHES, so the
# full evaluator rejects it at the EQUIVALENCE gate (not correctness). Found by
# materializing each break, running its suite, and checking corpus equivalence.
EQ_BREAK = {
    "task_scheduler": "uncommon_cancel_running_counter",
}

# A break that the test suite itself catches, so the evaluator rejects it at the
# CORRECTNESS gate (tests-failed) before equivalence ever runs.
TESTS_BREAK = {
    "rate_limiter": "drop_validation_ctor_rate",
}


def _entry(case):
    return json.loads((MCASES / case / "meta.json").read_text())["entry"]


@pytest.mark.parametrize("case", CASES)
def test_reference_passes_both_gates_and_scores_at_floor(case):
    e = evaluate(MCASES / case, MCASES / case / "reference")
    assert e.verdict == "scored", e.feedback
    assert e.reason_code is None and e.gate is None
    assert e.weighted_cost == 0.0  # the reference IS the floor
    assert e.metrics is not None and e.metric_costs is not None
    assert "PASSED the correctness and equivalence gates" in e.feedback


@pytest.mark.parametrize("case", CASES)
def test_original_passes_both_gates_and_scores_worse(case):
    ref = evaluate(MCASES / case, MCASES / case / "reference")
    orig = evaluate(MCASES / case, MCASES / case / "original")
    assert orig.verdict == "scored", orig.feedback
    assert orig.weighted_cost > ref.weighted_cost
    assert orig.weighted_cost == pytest.approx(1.0)  # the original anchors 1.0
    # Scored-but-above-floor feedback names specific metrics and files.
    assert "Largest weighted gaps from the reference floor" in orig.feedback


def test_failing_test_candidate_rejected_at_correctness(tmp_path):
    case = "rate_limiter"
    brk = next(
        b
        for b in _load_module(MCASES / case / "breaks.py").BREAKS
        if b["name"] == TESTS_BREAK[case]
    )
    broken = _materialize_break(MCASES / case / "original", brk, tmp_path)
    e = evaluate(MCASES / case, broken)
    assert e.verdict == "rejected"
    assert e.reason_code == "tests-failed"
    assert e.gate == "tests"
    assert e.weighted_cost is None and e.metrics is None  # never scored
    assert "REJECTED at the correctness gate" in e.feedback


def test_planted_break_rejected_at_equivalence_with_witness(tmp_path):
    case = "task_scheduler"
    brk = next(
        b
        for b in _load_module(MCASES / case / "breaks.py").BREAKS
        if b["name"] == EQ_BREAK[case]
    )
    broken = _materialize_break(MCASES / case / "original", brk, tmp_path)
    e = evaluate(MCASES / case, broken)
    assert e.verdict == "rejected"
    assert e.reason_code == NON_EQUIVALENT
    assert e.gate == "equivalence"
    assert e.weighted_cost is None and e.metrics is None  # never scored
    # The feedback names the first diverging sequence and the call.
    assert "First diverging sequence: deep_cancel_heavy" in e.feedback
    assert "('stats', ())" in e.feedback


def test_result_shape_mirrors_v1_contract(tmp_path):
    """Scored and rejected results both carry the v1 evaluator's fields."""
    fields = (
        "verdict",
        "reason_code",
        "gate",
        "metrics",
        "weighted_cost",
        "metric_costs",
        "flags",
        "feedback",
    )
    scored = evaluate(MCASES / "rate_limiter", MCASES / "rate_limiter" / "reference")
    for f in fields:
        assert hasattr(scored, f)
    assert scored.reason_code is None and scored.weighted_cost is not None

    brk = next(
        b
        for b in _load_module(MCASES / "rate_limiter" / "breaks.py").BREAKS
        if b["name"] == TESTS_BREAK["rate_limiter"]
    )
    broken = _materialize_break(MCASES / "rate_limiter" / "original", brk, tmp_path)
    rejected = evaluate(MCASES / "rate_limiter", broken)
    for f in fields:
        assert hasattr(rejected, f)
    assert rejected.reason_code is not None and rejected.weighted_cost is None


def test_outcome_bloated_candidate_fails_closed(tmp_path):
    """Carried flag 1: a candidate whose per-call outcomes overflow mverify's
    1 MB read-back cap fails CLOSED to NOT EQUIVALENT (rejected, not crashed, not
    falsely equivalent). Exercised at the equivalence-gate level; see module
    docstring for why the full evaluator cannot reach the cap."""
    entry = _entry("rate_limiter")
    pkg = tmp_path / "bloat"
    pkg.mkdir()
    # Loadable, every public method runs without error, but the observable
    # outcomes are huge, so the emitted frame exceeds the 1 MB read-back cap.
    big = "'x' * 60000"
    (pkg / "__init__.py").write_text(
        f"class {entry}:\n"
        "    def __init__(self, *a, **k):\n"
        "        pass\n"
        f"    def allow(self, *a, **k):\n        return {big}\n"
        f"    def remaining(self, *a, **k):\n        return {big}\n"
        "    def tick(self, *a, **k):\n        return 0\n"
        "    def reset(self, *a, **k):\n        return True\n"
        "    def active_clients(self, *a, **k):\n        return []\n"
        f"    def stats(self, *a, **k):\n        return {big}\n",
        encoding="utf-8",
    )

    eq, witness, stats = check_equivalence_containerized(MCASES / "rate_limiter", pkg)
    assert eq is False  # NOT falsely equivalent
    assert witness is None  # no per-call witness on a fail-closed run
    assert "error" in stats  # the failure reason is carried
