"""Direct unit tests for the orchestrator loop.run_loop (H1, P7.2).

run_loop is the single-function engine's orchestrator: it establishes the baseline,
drives generate -> evaluate -> feedback, and decides when to stop and what to return.
It was exercised only indirectly (through the benchmark and end-to-end runs), so a
regression in one of its guarantees could pass the suite. These tests pin each
guarantee directly, with NO live model and NO Docker: generator.generate and
evaluator.evaluate are replaced by deterministic fakes, and the case / runs
directories are tmp dirs, so the tests run in any environment, Docker-free included.

The guarantees, each as a test that fails if it regresses:
  1. never-worse fallback  -- no candidate beats the baseline -> the baseline original
                              is returned unchanged;
  2. generation cap        -- candidates keep improving but never plateau or reach the
                              floor -> exactly `cap` generations, stopped on the cap;
  3. plateau stop          -- candidates stop improving -> halt after plateau_limit,
                              via the invalid path AND the valid-but-not-improved path;
plus the floor early-stop, the anthropic.APIError halt, the feedback sanitization
(Fork 3: never forward the oracle), and the summary renderer / CLI entry point.

  cd tools && python -m pytest test_loop.py -q -p no:cacheprovider
"""

import io
import logging
import sys

import anthropic
import httpx
import pytest

from darwin import evaluator
from darwin import generator
from darwin import loop
from darwin.verify_case import BEHAVIOR_MISMATCH, COULD_NOT_RUN, TESTS_FAILED

ORIGINAL_SRC = "def f(x):\n    return x + 1\n"


# --- deterministic fakes for the two collaborators run_loop drives ----------
class _FakeGenerate:
    """Stand-in for generator.generate: returns queued GenResults in order. A queued
    Exception is RAISED instead of returned, modelling the loop's single halting
    condition (an API failure after the SDK's own retries)."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __call__(self, meta, original_code, prev_code, prev_feedback, model):
        self.calls.append((prev_code, prev_feedback))
        item = self._results.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class _FakeEvaluate:
    """Stand-in for evaluator.evaluate: the baseline call (on original.py) returns the
    baseline Evaluation; every candidate generation pops the next queued one."""

    def __init__(self, baseline, candidates):
        self._baseline = baseline
        self._candidates = list(candidates)
        self.candidate_paths = []

    def __call__(self, candidate_path, case_dir, timeout=10.0):
        if str(candidate_path).endswith("original.py"):
            return self._baseline
        self.candidate_paths.append(str(candidate_path))
        return self._candidates.pop(0)


def _scored(weighted_cost, feedback="metrics-only feedback (safe to forward)"):
    """A passing (scored) Evaluation at the given weighted_cost (0.0 = floor, lower is
    better)."""
    return evaluator.Evaluation(
        "scored", None, None, {}, weighted_cost, {}, [], feedback
    )


def _rejected(reason_code=TESTS_FAILED, gate="tests"):
    """A gate-rejected Evaluation (not scored: no metrics, no weighted_cost)."""
    return evaluator.Evaluation(
        "rejected",
        reason_code,
        gate,
        None,
        None,
        None,
        [],
        f"REJECTED at the {gate} gate (reason: {reason_code}).",
    )


def _valid(code):
    """A valid GenResult carrying `code` (parses and defines the entry point)."""
    return generator.GenResult(
        code, "```python\n" + code + "```", True, None, "fake-model", 10, 20, 0.001
    )


def _invalid(error="your output was not valid Python: SyntaxError"):
    """An invalid GenResult: no usable code; the loop feeds the error back."""
    return generator.GenResult(
        None, "prose, no code block", False, error, "fake-model", 5, 5, 0.0005
    )


def _api_error():
    """A real anthropic.APIError (the one halting condition the loop catches)."""
    return anthropic.APIError(
        "simulated API failure",
        httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        body=None,
    )


@pytest.fixture
def case(tmp_path, monkeypatch):
    """A throwaway case dir (meta.json + original.py) with loop.CASES / loop.RUNS
    pointed at tmp dirs and request_provenance stubbed, so run_loop touches no real
    case, writes under tmp only, and needs no model client. Returns the case name."""
    name = "demo_case"
    cdir = tmp_path / "cases" / name
    cdir.mkdir(parents=True)
    (cdir / "meta.json").write_text(
        '{"case_id": "demo_case", "entry_point": "f"}', encoding="utf-8"
    )
    (cdir / "original.py").write_text(ORIGINAL_SRC, encoding="utf-8")
    monkeypatch.setattr(loop, "CASES", tmp_path / "cases")
    monkeypatch.setattr(loop, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(
        generator, "request_provenance", lambda model: {"model": model, "stubbed": True}
    )
    return name


def _patch_engine(monkeypatch, gen, ev):
    """Replace the two collaborators run_loop calls. generator.generate is patched on
    the module (loop resolves it through the module each call); evaluate is patched on
    loop, where the from-import bound the name."""
    monkeypatch.setattr(generator, "generate", gen)
    monkeypatch.setattr(loop, "evaluate", ev)


# --- guarantee 1: never-worse fallback --------------------------------------
def test_never_worse_returns_baseline_when_nothing_improves(case, monkeypatch):
    """Guarantee 1. With every candidate worse-scored, gate-rejected, or invalid, the
    loop returns the baseline original unchanged: returned == baseline-original, the
    best cost equals the baseline cost, and best.py is byte-identical to original.py."""
    baseline = _scored(1.0)
    gen = _FakeGenerate(
        [
            _valid("def f(x):\n    return x + 1  # worse\n"),  # -> worse-scored
            _valid("def f(x):\n    return x + 1  # rejected\n"),  # -> gate-rejected
            _invalid(),  # -> invalid
        ]
    )
    ev = _FakeEvaluate(baseline, [_scored(2.0), _rejected()])
    _patch_engine(monkeypatch, gen, ev)

    # plateau_limit high so the plateau never cuts the run short: this isolates the
    # never-worse decision across a full cap=3 run (worse + rejected + invalid, none
    # of which is an improvement).
    summary, run_dir = loop.run_loop(case, cap=3, plateau_limit=5)

    assert summary["returned"] == "baseline-original"
    assert summary["best_weighted_cost"] == baseline.weighted_cost == 1.0
    assert summary["improved_over_baseline"] is False
    assert (run_dir / "best.py").read_text(encoding="utf-8") == ORIGINAL_SRC
    assert summary["generations"] == 3


# --- guarantee 2: generation cap --------------------------------------------
def test_generation_cap_stops_after_exactly_cap(case, monkeypatch):
    """Guarantee 2. Candidates keep improving but never reach the floor and never
    plateau, so the loop runs exactly `cap` generations and stops on the cap (not on
    the floor and not on an API halt)."""
    baseline = _scored(1.0)
    codes = [f"def f(x):\n    return x + 1  # gen{n}\n" for n in range(1, 5)]
    gen = _FakeGenerate([_valid(c) for c in codes])
    # strictly decreasing, all above the floor (0.0): every generation improves, so
    # the plateau counter resets each time and never triggers.
    ev = _FakeEvaluate(baseline, [_scored(c) for c in (0.9, 0.8, 0.7, 0.6)])
    _patch_engine(monkeypatch, gen, ev)

    summary, run_dir = loop.run_loop(case, cap=4, plateau_limit=2)

    assert summary["generations"] == 4  # exactly cap
    assert summary["halted"] is None  # not an API halt
    assert summary["best_weighted_cost"] == 0.6  # above floor -> not a floor stop
    assert summary["returned"] == "best-candidate"
    assert (run_dir / "best.py").read_text(encoding="utf-8") == codes[-1]
    assert gen.calls[0] == (None, None)  # gen 1 sees no prior (Fork 1)


# --- guarantee 3: plateau stop (both increment paths) -----------------------
def test_plateau_stop_via_invalid_candidates(case, monkeypatch):
    """Guarantee 3a. Consecutive INVALID candidates (g.valid False) each increment the
    plateau; the loop halts after plateau_limit of them, well before the cap, and
    nothing was scored so the baseline is returned."""
    baseline = _scored(1.0)
    gen = _FakeGenerate([_invalid(), _invalid(), _invalid()])  # 3rd never reached
    ev = _FakeEvaluate(baseline, [])  # invalid -> no evaluate
    _patch_engine(monkeypatch, gen, ev)

    summary, _ = loop.run_loop(case, cap=10, plateau_limit=2)

    assert summary["generations"] == 2  # stopped at plateau, far below cap
    assert summary["returned"] == "baseline-original"
    assert summary["halted"] is None
    assert ev.candidate_paths == []  # no candidate was ever scored
    assert len(gen.calls) == 2  # generation stopped on the 2nd


def test_plateau_stop_via_valid_not_improved(case, monkeypatch):
    """Guarantee 3b. After an improvement, consecutive VALID-but-not-improving scored
    candidates increment the plateau; the loop halts after plateau_limit, before the
    cap, and returns the one improvement it found."""
    baseline = _scored(1.0)
    codes = [f"def f(x):\n    return x + 1  # g{n}\n" for n in (1, 2, 3)]
    gen = _FakeGenerate([_valid(c) for c in codes])
    # 0.5 improves (new best); 0.5 again does NOT (not < best); 0.6 does NOT -> the
    # plateau reaches the limit of 2 and the loop stops.
    ev = _FakeEvaluate(baseline, [_scored(0.5), _scored(0.5), _scored(0.6)])
    _patch_engine(monkeypatch, gen, ev)

    summary, run_dir = loop.run_loop(case, cap=10, plateau_limit=2)

    assert summary["generations"] == 3  # stopped at plateau, below cap
    assert summary["best_weighted_cost"] == 0.5  # the first (only) improvement
    assert summary["returned"] == "best-candidate"
    assert (run_dir / "best.py").read_text(encoding="utf-8") == codes[0]


# --- floor early-stop -------------------------------------------------------
def test_floor_reached_stops_immediately(case, monkeypatch):
    """A scored candidate at weighted_cost <= FLOOR_REACHED halts the loop at once,
    well before the cap, and is returned as the best."""
    baseline = _scored(1.0)
    floor_code = "def f(x):\n    return x + 1  # at the floor\n"
    gen = _FakeGenerate([_valid(floor_code), _valid("def f(x):\n    return 0\n")])
    ev = _FakeEvaluate(baseline, [_scored(loop.FLOOR_REACHED)])  # 0.0 -> at the floor
    _patch_engine(monkeypatch, gen, ev)

    summary, run_dir = loop.run_loop(case, cap=5, plateau_limit=2)

    assert summary["generations"] == 1  # one generation, then floor stop
    assert summary["best_weighted_cost"] == loop.FLOOR_REACHED
    assert summary["returned"] == "best-candidate"
    assert (run_dir / "best.py").read_text(encoding="utf-8") == floor_code
    assert len(gen.calls) == 1  # the 2nd candidate is never made


# --- the API-failure halt ---------------------------------------------------
def test_api_error_halts_and_returns_best_so_far(case, monkeypatch):
    """generator.generate raising anthropic.APIError is the one halting condition: the
    loop stops, records the halt, and returns the best candidate found so far."""
    baseline = _scored(1.0)
    good_code = "def f(x):\n    return x + 1  # improved\n"
    gen = _FakeGenerate([_valid(good_code), _api_error()])  # gen 2 raises
    ev = _FakeEvaluate(baseline, [_scored(0.7)])
    _patch_engine(monkeypatch, gen, ev)

    summary, run_dir = loop.run_loop(case, cap=5, plateau_limit=2)

    assert summary["halted"] is not None
    assert "APIError" in summary["halted"]
    assert summary["best_weighted_cost"] == 0.7  # the best found before the halt
    assert summary["returned"] == "best-candidate"
    assert (run_dir / "best.py").read_text(encoding="utf-8") == good_code
    assert summary["generations"] == 1  # the halted generation records nothing


def test_api_error_on_first_generation_returns_baseline(case, monkeypatch):
    """If the halt strikes before any candidate improves, never-worse still holds: the
    baseline original is returned, with the halt recorded."""
    baseline = _scored(1.0)
    gen = _FakeGenerate([_api_error()])
    ev = _FakeEvaluate(baseline, [])
    _patch_engine(monkeypatch, gen, ev)

    summary, run_dir = loop.run_loop(case, cap=5, plateau_limit=2)

    assert summary["halted"] is not None
    assert summary["returned"] == "baseline-original"
    assert summary["best_weighted_cost"] == 1.0
    assert (run_dir / "best.py").read_text(encoding="utf-8") == ORIGINAL_SRC
    assert summary["generations"] == 0


# --- feedback sanitization (Fork 3: the generator never sees the oracle) -----
def test_format_feedback_scored_is_forwarded_verbatim():
    """A SCORED candidate's feedback is metric/floor data only (no oracle), so it is
    forwarded as-is."""
    ev = _scored(0.4, feedback="Largest weighted gaps: cyclomatic_total=...")
    assert loop.format_feedback(ev) == ev.feedback


def test_format_feedback_strips_oracle_from_behavior_mismatch():
    """A behavior-mismatch rejection's raw reason embeds the expected OUTPUT
    ("expected R, got R"). format_feedback rebuilds it to name the diverging INPUT
    (Fork 1) but never the expected output (Fork 3)."""
    oracle = "EXPECTED_ORACLE_VALUE_9f3a"
    raw = f"golden mismatch for args=[1, 2] kwargs={{}}: expected {oracle!r}, got 7"
    ev = evaluator.Evaluation(
        "rejected", BEHAVIOR_MISMATCH, "golden", None, None, None, [], raw
    )

    assert oracle in ev.feedback  # precondition: raw reason has it
    out = loop.format_feedback(ev)
    assert oracle not in out  # the expected output never leaks
    assert "args=[1, 2] kwargs={}" in out  # the diverging INPUT is named
    assert "Restore the original behavior" in out


def test_format_feedback_tests_failed_is_generic():
    """A tests-failed rejection forwards a generic behavior-changed message (the pytest
    dump, which can print the oracle, is NOT forwarded)."""
    ev = _rejected(TESTS_FAILED, "tests")
    out = loop.format_feedback(ev)
    assert "REJECTED at the tests gate" in out
    assert "Re-examine your changes" in out


def test_format_feedback_forwards_run_error_tail():
    """A could-not-run / crashed / timed-out rejection is about the candidate's own
    execution (safe and useful), so a short tail of the detail is forwarded."""
    detail = "Traceback ...\nNameError: name 'helper' is not defined"
    ev = evaluator.Evaluation(
        "rejected", COULD_NOT_RUN, "tests", None, None, None, [], detail
    )
    out = loop.format_feedback(ev)
    assert "REJECTED at the tests gate" in out
    assert "NameError" in out


# --- the summary renderer and the CLI entry point ---------------------------
def _render_summary(summary, run_dir):
    """Drive loop._log_summary, capturing the operational log it emits. The 'darwin'
    namespace has propagate=False and no test-time level, so a handler is attached
    directly to loop's logger and its state restored afterwards."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    logger = loop.log
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        loop._log_summary(summary, run_dir)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    return stream.getvalue()


def test_log_summary_renders_every_record_kind():
    """_log_summary renders each trace record kind (baseline / scored / rejected /
    invalid), the per-generation metric line, and the API-halt warning, surfacing the
    run's key facts -- a guard that the summary shape and the operational log stay in
    sync."""
    metrics = {
        "cyclomatic_total": 4,
        "logical_loc": 6,
        "dependency_count": 1,
        "dead_code_count": 1,
        "max_nesting_depth": 2,
        "maintainability_index": 80.0,
    }
    summary = {
        "case": "demo_case",
        "model": "fake-model",
        "config": {"cap": 5, "plateau_limit": 2},
        "baseline_weighted_cost": 1.0,
        "best_weighted_cost": 0.3,
        "improved_over_baseline": True,
        "returned": "best-candidate",
        "halted": "APIError: boom",
        "generations": 3,
        "total_input_tokens": 30,
        "total_output_tokens": 60,
        "total_cost_usd": 0.01,
        "trace": [
            {"generation": 0, "verdict": "baseline", "weighted_cost": 1.0},
            {
                "generation": 1,
                "verdict": "scored",
                "weighted_cost": 0.3,
                "flags": ["suspiciously-simple"],
                "is_improvement": True,
                "metrics": metrics,
                "feedback_given": "PASSED the gates.",
            },
            {
                "generation": 2,
                "verdict": "rejected",
                "reason_code": TESTS_FAILED,
                "gate": "tests",
                "feedback_given": "REJECTED at the tests gate.",
            },
            {
                "generation": 3,
                "verdict": "invalid",
                "feedback_given": "your output was not valid Python",
            },
        ],
    }

    text = _render_summary(summary, "runs/demo_case_x")

    assert "BASELINE" in text
    assert "SCORED" in text
    assert "REJECTED" in text
    assert "INVALID" in text
    assert "cyc_total=4 lloc=6" in text  # the per-generation metric line
    assert "HALTED" in text  # the API-halt warning
    assert "returned best-candidate" in text


def test_main_runs_loop_for_a_valid_case(case, monkeypatch):
    """The CLI entry point resolves the case under loop.CASES, configures logging once,
    runs the loop, and hands the summary to the renderer."""
    captured = {}
    monkeypatch.setattr(loop, "run_loop", lambda *a, **k: ({"sentinel": True}, "rd"))
    monkeypatch.setattr(loop, "_log_summary", lambda s, rd: captured.update(s=s, rd=rd))
    monkeypatch.setattr(loop.logsetup, "configure", lambda: None)
    monkeypatch.setattr(sys, "argv", ["loop.py", case])

    loop.main()

    assert captured["s"] == {"sentinel": True}
    assert captured["rd"] == "rd"


def test_main_exits_on_unknown_case(case, monkeypatch):
    """main fails fast (does not run the loop) when the case directory is absent."""
    monkeypatch.setattr(loop.logsetup, "configure", lambda: None)
    monkeypatch.setattr(sys, "argv", ["loop.py", "no_such_case"])

    with pytest.raises(SystemExit):
        loop.main()
