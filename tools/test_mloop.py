"""Tests for the multi-file loop (Phase V2).

Tier a (no API key, no Docker): drives scripted (generation, evaluation) results
through the injectable seams to prove baseline fallback, never-worse-than-baseline,
plateau / floor stops, invalid-not-terminal, API-failure-halts, fresh per-generation
directories (FLAG 2), and the full FLAG 1 sanitization matrix -- including the proof
that a sentinel placed in witness['original'] never reaches the feedback and that a
tests-failed rejection yields no pytest dump.

Tier b (Docker-gated, no API key): one real loop run on rate_limiter with a scripted
fake generator that emits real candidate packages (the original files as a non-
improving generation, the reference files as an improving one), evaluated through the
REAL mevaluator, asserting the loop returns the better one and never worse than
baseline. Skips cleanly if the Docker sandbox image is absent.
"""
import json
import subprocess
from types import SimpleNamespace

import anthropic
import httpx
import pytest

import mevaluator
import mgenerator
import mloop
from sandbox_container import IMAGE as SANDBOX_IMAGE
from verify_case import COULD_NOT_RUN, TESTS_FAILED

CASE = "rate_limiter"

# A minimal, path-safe candidate package the loop can materialize without Docker.
VALID_FILES = {
    "__init__.py": "from .core import Limiter\n",
    "core.py": "class Limiter:\n    def __init__(self, rate, burst):\n        self.rate = rate\n",
}


# ------------------------------------------------------------- builders

def gen_result(valid=True, files=None, error=None, model="fake-model",
               in_t=100, out_t=200, cost=0.0015):
    return mgenerator.MGenResult(
        files=(VALID_FILES if files is None else files), raw_text="", valid=valid,
        error=error, candidate_dir=None, model=model,
        input_tokens=in_t, output_tokens=out_t, cost_usd=cost)


def meval(verdict="scored", cost=None, gate=None, reason=None, flags=None,
          metrics=None, feedback=""):
    return mevaluator.MEvaluation(
        verdict=verdict, reason_code=reason, gate=gate, metrics=metrics,
        weighted_cost=cost, metric_costs=None, flags=(flags or []), feedback=feedback)


class FakeGen:
    """Scripted generation seam. Records the prev_files / prev_feedback each call
    was handed (to assert Fork 1 forwarding); a scripted Exception is raised."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, meta, original_files, prev_files=None, prev_feedback=None,
                 model=None, client=None):
        self.calls.append(SimpleNamespace(prev_files=prev_files, prev_feedback=prev_feedback))
        item = self.results.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class FakeEval:
    """Scripted evaluation seam. Records the candidate dir each call evaluated."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, case_dir, candidate_dir, timeout=30.0):
        self.calls.append(str(candidate_dir))
        return self.results.pop(0)


def _agg():
    return {"aggregate": {"file_count": 4}}  # placeholder metrics for a scored record


# =========================================================== tier a: orchestration

def test_baseline_fallback_never_worse(tmp_path):
    fg = FakeGen([gen_result(), gen_result()])
    fe = FakeEval([
        meval("scored", cost=1.0, metrics=_agg()),                       # baseline
        meval("rejected", gate="equivalence", reason=mevaluator.NON_EQUIVALENT,
              feedback="REJECTED at the equivalence gate.\nFailed closed (no verifiable replay): boom"),
        meval("rejected", gate="tests", reason=TESTS_FAILED,
              feedback="REJECTED at the correctness gate.\nE assert x == 5"),
    ])
    s, _ = mloop.run_loop(CASE, cap=5, plateau_limit=2, generate=fg, evaluate=fe,
                          run_root=tmp_path)
    assert s["improved_over_baseline"] is False
    assert s["returned"] == "baseline-original"
    assert s["best_weighted_cost"] == 1.0
    assert s["generations"] == 2                       # plateau hit after two rejections


def test_improvement_then_floor_stop(tmp_path):
    fg = FakeGen([gen_result(), gen_result(), gen_result()])
    fe = FakeEval([
        meval("scored", cost=1.0, metrics=_agg()),     # baseline
        meval("scored", cost=0.4, metrics=_agg()),     # gen1 improved
        meval("scored", cost=0.0, metrics=_agg()),     # gen2 floor
    ])
    s, rd = mloop.run_loop(CASE, cap=5, plateau_limit=3, generate=fg, evaluate=fe,
                           run_root=tmp_path)
    assert s["improved_over_baseline"] is True
    assert s["best_weighted_cost"] == 0.0
    assert s["returned"] == "best-candidate"
    assert s["generations"] == 2                       # floor stop, gen3 never run

    # The load-bearing fields are recorded faithfully on disk.
    rec2 = json.loads((rd / "gen_02.json").read_text(encoding="utf-8"))
    assert rec2["weighted_cost"] == 0.0 and rec2["is_improvement"] is True
    rec1 = json.loads((rd / "gen_01.json").read_text(encoding="utf-8"))
    assert rec1["weighted_cost"] == 0.4 and rec1["is_improvement"] is True


def test_plateau_stop(tmp_path):
    fg = FakeGen([gen_result(), gen_result(), gen_result()])
    fe = FakeEval([
        meval("scored", cost=1.0, metrics=_agg()),     # baseline
        meval("scored", cost=0.5, metrics=_agg()),     # gen1 improved   plateau 0
        meval("scored", cost=0.6, metrics=_agg()),     # gen2 no-improve plateau 1
        meval("scored", cost=0.55, metrics=_agg()),    # gen3 no-improve plateau 2 -> stop
    ])
    s, _ = mloop.run_loop(CASE, cap=5, plateau_limit=2, generate=fg, evaluate=fe,
                          run_root=tmp_path)
    assert s["best_weighted_cost"] == 0.5
    assert s["returned"] == "best-candidate"
    assert s["generations"] == 3


def test_invalid_not_terminal_and_feedback_forwarded(tmp_path):
    invalid_files = {"__init__.py": "from .x import Limiter\n"}
    invalid_error = "your response contained no `### FILE:` blocks at all; emit each file ..."
    fg = FakeGen([
        gen_result(valid=False, files=invalid_files, error=invalid_error),
        gen_result(valid=True, files=VALID_FILES),
    ])
    fe = FakeEval([
        meval("scored", cost=1.0, metrics=_agg()),     # baseline
        meval("scored", cost=0.3, metrics=_agg()),     # gen2 (the valid one)
    ])
    s, _ = mloop.run_loop(CASE, cap=2, plateau_limit=5, generate=fg, evaluate=fe,
                          run_root=tmp_path)
    assert s["generations"] == 2
    assert s["best_weighted_cost"] == 0.3
    assert s["trace"][1]["verdict"] == "invalid"       # gen1 invalid, not terminal
    assert s["trace"][2]["verdict"] == "scored" and s["trace"][2]["is_improvement"] is True
    # Fork 1: gen2 was handed gen1's files and gen1's error as feedback, verbatim.
    assert fg.calls[1].prev_files == invalid_files
    assert fg.calls[1].prev_feedback == invalid_error


def test_api_failure_halts(tmp_path):
    err = anthropic.APIError(
        "boom", request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        body=None)
    fg = FakeGen([err])
    fe = FakeEval([meval("scored", cost=1.0, metrics=_agg())])   # baseline only
    s, _ = mloop.run_loop(CASE, cap=5, plateau_limit=2, generate=fg, evaluate=fe,
                          run_root=tmp_path)
    assert s["halted"] is not None and "APIError" in s["halted"]
    assert s["returned"] == "baseline-original"
    assert s["generations"] == 0                       # halted before any generation landed


def test_fresh_per_generation_directories(tmp_path):
    # gen1 emits an extra file; gen2 does not. A FRESH dir per generation means
    # gen2's directory must NOT contain gen1's stale file (FLAG 2).
    g1 = {"__init__.py": "from .core import Limiter\n",
          "core.py": "class Limiter:\n    pass\n",
          "stale_only_gen1.py": "X = 1\n"}
    g2 = {"__init__.py": "from .core import Limiter\n",
          "core.py": "class Limiter:\n    pass\n"}
    fg = FakeGen([gen_result(files=g1), gen_result(files=g2)])
    fe = FakeEval([
        meval("scored", cost=1.0, metrics=_agg()),     # baseline
        meval("scored", cost=0.5, metrics=_agg()),     # gen1 improved
        meval("scored", cost=0.6, metrics=_agg()),     # gen2 no-improve
    ])
    s, rd = mloop.run_loop(CASE, cap=2, plateau_limit=5, generate=fg, evaluate=fe,
                           run_root=tmp_path)
    d1, d2 = rd / "gen_01_candidate", rd / "gen_02_candidate"
    assert d1.is_dir() and d2.is_dir() and d1 != d2
    assert (d1 / "stale_only_gen1.py").exists()
    assert not (d2 / "stale_only_gen1.py").exists()    # gen2 dir is fresh, not reused
    assert (rd / "gen_00_baseline").is_dir()           # baseline has its own dir too
    cand_dirs = [r["candidate_dir"] for r in s["trace"] if r["candidate_dir"]]
    assert len(cand_dirs) == len(set(cand_dirs))       # every dir distinct, none reused


# =========================================================== tier a: FLAG 1 matrix

def test_scored_feedback_forwarded_asis():
    ev = meval("scored", cost=0.3,
               feedback="PASSED the correctness and equivalence gates. Weighted "
                        "complexity cost 0.3. Largest weighted gaps ...")
    assert mloop.format_feedback(ev) == ev.feedback


def test_equivalence_witness_does_not_leak_oracle():
    # Build feedback with the REAL mevaluator helper so the sanitizer is tested
    # against the actual output format, with a sentinel as the oracle's outcome.
    witness = {"sequence": "seq_collision_7", "call_index": 3,
               "call": "('allow', ('client-x',))",
               "original": "ORACLE_SENTINEL_9f3", "candidate": "['bool', False]"}
    fb = mevaluator._reject_equivalence_feedback(witness, {"calls_compared": 10, "sequences": 5})
    ev = meval("rejected", gate="equivalence", reason=mevaluator.NON_EQUIVALENT, feedback=fb)
    out = mloop.format_feedback(ev)
    assert "ORACLE_SENTINEL_9f3" not in out             # the oracle outcome never leaks
    assert "['bool', False]" not in out                 # candidate outcome dropped too
    assert "seq_collision_7" in out                     # the diverging INPUT is named (Fork 1)
    assert "First diverging sequence" in out


def test_equivalence_failclosed_forwards_candidate_error():
    fb = mevaluator._reject_equivalence_feedback(
        None, {"error": "candidate failed to replay: ModuleNotFoundError: "
                        "No module named 'candidate.helpers'"})
    ev = meval("rejected", gate="equivalence", reason=mevaluator.NON_EQUIVALENT, feedback=fb)
    out = mloop.format_feedback(ev)
    assert "Failed closed" in out
    assert "ModuleNotFoundError" in out                 # candidate's OWN replay failure (safe)


def test_tests_failed_generic_no_dump():
    dump = ("REJECTED at the correctness gate (reason: tests-failed). Not scored: ...\n"
            "E       assert limiter.allow('x') == EXPECTED_SENTINEL_42")
    fb = mevaluator._reject_tests_feedback(TESTS_FAILED, dump)
    ev = meval("rejected", gate="tests", reason=TESTS_FAILED, feedback=fb)
    out = mloop.format_feedback(ev)
    assert "EXPECTED_SENTINEL_42" not in out            # no oracle from the assertion dump
    assert "pytest" not in out.lower()
    assert "Re-examine your changes" in out             # the generic behavior-changed message


def test_could_not_run_forwards_candidate_error():
    # V2-P2 observation 5: a missing subpackage __init__ surfaces as could-not-run;
    # the candidate's own error is safe and useful, so it is forwarded.
    fb = mevaluator._reject_tests_feedback(
        COULD_NOT_RUN, "Traceback (most recent call last):\n  ...\n"
                       "ModuleNotFoundError: No module named 'candidate.refill'")
    ev = meval("rejected", gate="tests", reason=COULD_NOT_RUN, feedback=fb)
    out = mloop.format_feedback(ev)
    assert "ModuleNotFoundError" in out
    assert "candidate.refill" in out


# =========================================================== tier b: real loop (Docker)

def _docker_available():
    try:
        r = subprocess.run(["docker", "image", "inspect", SANDBOX_IMAGE],
                           capture_output=True)
        return r.returncode == 0
    except (FileNotFoundError, OSError):
        return False


@pytest.mark.skipif(not _docker_available(),
                    reason=f"Docker sandbox image {SANDBOX_IMAGE} not available")
def test_real_loop_returns_better_candidate(tmp_path):
    # No API key: the generator is faked to emit real candidate packages. The
    # ORIGINAL files are a non-improving generation; the REFERENCE files are the
    # improving one (the floor). Evaluation goes through the REAL mevaluator
    # (container gates + metrics).
    original_files = mgenerator.read_unit(mloop.MCASES / CASE / "original")
    reference_files = mgenerator.read_unit(mloop.MCASES / CASE / "reference")
    fg = FakeGen([gen_result(files=original_files), gen_result(files=reference_files)])
    s, _ = mloop.run_loop(CASE, cap=2, plateau_limit=5, generate=fg,
                          evaluate=mevaluator.evaluate, run_root=tmp_path, timeout=60.0)
    assert s["baseline_weighted_cost"] == 1.0
    assert s["improved_over_baseline"] is True
    assert s["best_weighted_cost"] <= s["baseline_weighted_cost"]   # never worse than baseline
    assert s["best_weighted_cost"] <= 0.0                            # the reference is the floor
    assert s["returned"] == "best-candidate"
