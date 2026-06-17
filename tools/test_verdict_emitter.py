"""Tests for the verdict-emission seam (P6.4.2, decision 0032).

Two tiers:

Tier a (no API key, no Docker): the serialization round-trip (to_dict/from_dict
lossless for the scored and the rejected shapes, including the None fields and
across a real JSON hop), that mevaluator.main() now serializes via to_dict, that
InProcessEmitter and a test fake both satisfy the VerdictEmitter Protocol, that
InProcessEmitter.emit returns its delegate's result unchanged and forwards the
arguments, and the swappability proof -- a test-only fake VerdictEmitter injected
into run_loop drives the loop to completion on canned verdicts, with no change to
run_loop's body.

Tier b (Docker-gated, no API key): the default InProcessEmitter returns a verdict
EQUAL to evaluate() for a real scored case, and emit returns evaluate()'s exact
result unchanged for a real scored and a real rejected case. Skips cleanly if the
sandbox image is absent.

The fake emitter here is the ONLY non-in-process emitter that exists; it is test
code, never shipped (decision 0032: one protocol, one shipped implementation).
"""
import json
import sys
from types import SimpleNamespace

import pytest

import mevaluator
import mgenerator
import mloop
import sandbox_container
from mevaluator import MEvaluation, evaluate
from sandbox_container import IMAGE as SANDBOX_IMAGE
from validate_mcase import MCASES, _load_module, _materialize_break
from verdict_emitter import InProcessEmitter, VerdictEmitter

CASE = "rate_limiter"

# A minimal, path-safe candidate package run_loop can materialize without Docker.
VALID_FILES = {
    "__init__.py": "from .core import Limiter\n",
    "core.py": "class Limiter:\n    def __init__(self, rate, burst):\n        self.rate = rate\n",
}


# ------------------------------------------------------------- canned verdicts

def _scored(cost=0.3, feedback="PASSED the correctness and equivalence gates."):
    """A scored MEvaluation in the real scored shape (metrics/weighted_cost/
    metric_costs/flags all populated)."""
    return MEvaluation("scored", None, None,
                       {"aggregate": {"file_count": 2}, "per_file": {}},
                       cost, {"logical_loc": 0.1}, ["suspiciously-simple"], feedback)


def _rejected(feedback="REJECTED at the correctness gate (reason: tests-failed)."):
    """A rejected MEvaluation in the real rejected shape (the scoring fields None)."""
    return MEvaluation("rejected", "tests-failed", "tests", None, None, None, [], feedback)


# ------------------------------------------------------------- test fakes

class _FakeEmitter:
    """Test-only VerdictEmitter: returns canned MEvaluations and records each emit.
    Implements the Protocol via emit(). Never shipped -- proves ANY VerdictEmitter
    swaps into run_loop, not just InProcessEmitter (decision 0032)."""

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = []

    def emit(self, case_dir, candidate_dir, timeout=30.0):
        self.calls.append(str(candidate_dir))
        return self.verdicts.pop(0)


class _FakeGen:
    """Scripted generation seam so the swappability test needs no API key."""

    def __init__(self, results):
        self.results = list(results)

    def __call__(self, meta, original_files, prev_files=None, prev_feedback=None,
                 model=None, client=None):
        return self.results.pop(0)


def _genresult(files=VALID_FILES):
    return mgenerator.MGenResult(
        files=files, raw_text="", valid=True, error=None, candidate_dir=None,
        model="fake-model", input_tokens=1, output_tokens=1, cost_usd=0.0)


# =========================================================== tier a: serialization

@pytest.mark.parametrize("ev", [_scored(), _rejected()], ids=["scored", "rejected"])
def test_to_dict_from_dict_roundtrip_lossless(ev):
    """to_dict/from_dict round-trip losslessly for BOTH shapes, including the None
    fields of a rejected verdict and across a real JSON hop (the boundary payload)."""
    d = ev.to_dict()
    assert set(d) == {"verdict", "reason_code", "gate", "metrics",
                      "weighted_cost", "metric_costs", "flags", "feedback"}
    assert json.loads(json.dumps(d)) == d            # JSON-ready, no custom encoder
    assert MEvaluation.from_dict(d) == ev            # lossless inverse
    assert MEvaluation.from_dict(json.loads(json.dumps(d))) == ev   # survives a JSON hop


def test_main_uses_to_dict(monkeypatch):
    """mevaluator.main() serializes the verdict via to_dict (the single boundary
    shape), not an ad-hoc dict: the JSON it logs equals e.to_dict()."""
    ev = _scored(cost=0.42)
    monkeypatch.setattr(mevaluator, "evaluate", lambda *a, **k: ev)
    monkeypatch.setattr(mevaluator.logsetup, "configure", lambda *a, **k: None)
    recorded = []
    monkeypatch.setattr(mevaluator, "log",
                        SimpleNamespace(info=lambda *a, **k: recorded.append(a),
                                        warning=lambda *a, **k: None))
    monkeypatch.setattr(sys, "argv", ["mevaluator.py", "case_dir", "cand_dir"])
    mevaluator.main()
    first_message = recorded[0][0]                   # the first log.info is the verdict JSON
    assert json.loads(first_message) == ev.to_dict()


# =========================================================== tier a: the seam

def test_inprocess_emitter_and_fake_satisfy_protocol():
    """The shipped emitter and the test fake both satisfy the VerdictEmitter
    Protocol; a bare object without emit() does not."""
    assert isinstance(InProcessEmitter(), VerdictEmitter)
    assert isinstance(_FakeEmitter([]), VerdictEmitter)
    assert not isinstance(object(), VerdictEmitter)


@pytest.mark.parametrize("canned", [_scored(), _rejected()], ids=["scored", "rejected"])
def test_inprocess_emitter_returns_delegate_result_unchanged(canned):
    """InProcessEmitter.emit delegates to its evaluate and returns the result
    unchanged, forwarding (case_dir, candidate_dir, timeout), for both shapes."""
    seen = {}

    def fake_evaluate(case_dir, candidate_dir, timeout):
        seen["args"] = (case_dir, candidate_dir, timeout)
        return canned

    got = InProcessEmitter(evaluate=fake_evaluate).emit("CASE", "CAND", 12.5)
    assert got is canned                              # returned the delegate's object, unchanged
    assert seen["args"] == ("CASE", "CAND", 12.5)     # forwarded exactly


def test_fake_emitter_drives_run_loop_to_completion(tmp_path):
    """Swappability: a fake VerdictEmitter (NOT InProcessEmitter) injected into
    run_loop drives the loop to completion on its canned verdicts -- no Docker, no
    evaluate() call, and no change to run_loop's body to accommodate it."""
    fake = _FakeEmitter([_scored(cost=1.0), _scored(cost=0.0)])   # baseline=1.0, gen1 hits floor
    fg = _FakeGen([_genresult(), _genresult()])
    summary, _ = mloop.run_loop(CASE, cap=5, plateau_limit=2,
                                generate=fg, emitter=fake, run_root=tmp_path)
    assert summary["baseline_weighted_cost"] == 1.0
    assert summary["best_weighted_cost"] == 0.0       # reached the floor via the fake verdict
    assert summary["returned"] == "best-candidate"
    assert summary["improved_over_baseline"] is True
    assert len(fake.calls) == 2                        # baseline + gen 1, every verdict via emit


# =========================================================== tier b: real evaluate (Docker)

def _docker_available():
    # Use the production preflight (inspect-by-tag with a docker-image-ls fallback)
    # rather than a bare `docker image inspect`, so the containerd tag-resolution
    # false-negative does not skip these tests when the image IS present.
    try:
        sandbox_container._require_image(SANDBOX_IMAGE)
        return True
    except (RuntimeError, FileNotFoundError, OSError):
        return False


requires_docker = pytest.mark.skipif(
    not _docker_available(), reason=f"Docker sandbox image {SANDBOX_IMAGE} not available")


@requires_docker
def test_default_inprocess_emitter_equals_evaluate_scored():
    """The DEFAULT in-process emitter returns a verdict EQUAL to evaluate() for a
    real scored case (scored feedback is metric-derived and deterministic)."""
    case = MCASES / CASE
    ref = case / "reference"
    assert InProcessEmitter().emit(case, ref) == evaluate(case, ref)


@requires_docker
@pytest.mark.parametrize("kind", ["scored", "rejected"])
def test_inprocess_emit_returns_real_evaluate_unchanged(kind, tmp_path):
    """emit returns the REAL evaluate()'s exact result, unchanged, for a real scored
    and a real rejected case (identity, so the rejected feedback's volatile pytest
    duration cannot make this flaky)."""
    case = MCASES / CASE
    if kind == "scored":
        cand = case / "reference"
    else:
        brk = next(b for b in _load_module(case / "breaks.py").BREAKS
                   if b["name"] == "drop_validation_ctor_rate")
        cand = _materialize_break(case / "original", brk, tmp_path)
    seen = []

    def spy(c, d, t):                                  # the REAL evaluate, called once
        r = evaluate(c, d, t)
        seen.append(r)
        return r

    got = InProcessEmitter(evaluate=spy).emit(case, cand)
    assert got is seen[-1]                             # emit returned evaluate()'s exact result
    assert got.verdict == ("scored" if kind == "scored" else "rejected")
