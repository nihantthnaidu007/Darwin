"""Smoke guards for the four standalone harnesses that live under src/darwin/ but are NOT
collected by the suite (isolation_audit, bakeoff, verify_boundary, smoke_test). A
harness that is committed but never imported by a test can ship broken and green --
which is exactly what isolation_audit did: its _cmd_loop path called a nonexistent
loop._print_summary, so it crashed with AttributeError only when actually run.

Depth, stated honestly per harness:
  - isolation_audit: DRIVEN. _cmd_loop is exercised end to end with loop.run_loop,
    calibrate, and leak_check faked, so it runs Docker-free and model-free yet still
    reaches the real loop._log_summary call site -- the exact line that regressed.
    Reverting that fix makes test_isolation_audit_cmd_loop_renders_summary fail with
    AttributeError. The argparse parser is also built and its two subcommands parsed.
  - bakeoff, verify_boundary, smoke_test: IMPORT-PLUS-CALLABLE ONLY. Each does real
    work (Docker spin-ups, or seed-case evaluation through the real sandbox), so its
    guard imports the module cleanly and asserts a callable main(); it does NOT run
    main(). This bites an import-time or signature break, not a logic regression.

Docker-free and model-free: no live model call, no docker run, no image build. The
isolation_audit loop test fakes loop.run_loop; calibrate and leak_check (the two
Docker touch points _cmd_loop calls directly) are faked too, and nothing here imports
a real client or builds the sandbox image.

  cd tools && python -m pytest test_harness_smoke.py -q -p no:cacheprovider
"""

import importlib
import io
import logging
import sys
from types import SimpleNamespace

import pytest

from darwin import isolation_audit
from darwin import loop


# --- isolation_audit: the driven harness ------------------------------------
def _synthetic_summary():
    """A loop summary in the shape loop._log_summary renders, reusing the record kinds
    from test_loop.test_log_summary_renders_every_record_kind (baseline + scored)."""
    return {
        "case": "demo_case",
        "model": "fake-model",
        "config": {"cap": 5, "plateau_limit": 2},
        "baseline_weighted_cost": 1.0,
        "best_weighted_cost": 0.3,
        "improved_over_baseline": True,
        "returned": "best-candidate",
        "halted": None,
        "generations": 1,
        "total_input_tokens": 10,
        "total_output_tokens": 20,
        "total_cost_usd": 0.001,
        "trace": [
            {"generation": 0, "verdict": "baseline", "weighted_cost": 1.0},
            {
                "generation": 1,
                "verdict": "scored",
                "weighted_cost": 0.3,
                "flags": [],
                "is_improvement": True,
                "metrics": {
                    "cyclomatic_total": 4,
                    "logical_loc": 6,
                    "dependency_count": 1,
                    "dead_code_count": 0,
                    "max_nesting_depth": 2,
                    "maintainability_index": 80.0,
                },
                "feedback_given": "PASSED the gates.",
            },
        ],
    }


def test_isolation_audit_cmd_loop_renders_summary(tmp_path, monkeypatch):
    """_cmd_loop runs to completion and renders the run summary, with loop.run_loop,
    calibrate, and leak_check faked so it stays Docker-free and model-free. This BITES
    the _print_summary regression: _cmd_loop calls the REAL loop._log_summary, so
    reverting the fix (back to loop._print_summary) raises AttributeError right here."""
    summary = _synthetic_summary()
    run_dir = tmp_path / "demo_case_run"
    run_dir.mkdir()  # empty -> audit_candidates finds no candidate files, stays clean

    monkeypatch.setattr(
        isolation_audit,
        "calibrate",
        lambda n=5: {"n": n, "mean": 0.1, "median": 0.1, "min": 0.1, "max": 0.1},
    )
    monkeypatch.setattr(
        isolation_audit,
        "leak_check",
        lambda: {
            "leaked_containers": 0,
            "leaked_temp_artifacts": 0,
            "clean": True,
            "temp_samples": [],
        },
    )
    monkeypatch.setattr(loop, "run_loop", lambda *a, **k: (summary, run_dir))

    # Capture the operational log loop._log_summary emits. The 'darwin' logger has
    # propagate=False and no test-time level, so attach a handler directly and restore
    # it afterwards (mirrors test_loop._render_summary).
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    logger = loop.log
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        args = SimpleNamespace(case="demo_case", cap=5, plateau=2, model="fake-model")
        isolation_audit._cmd_loop(args)  # must complete without error
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)

    rendered = stream.getvalue()
    assert "CASE demo_case" in rendered  # the summary header rendered
    assert "returned best-candidate" in rendered  # the summary footer rendered


def test_isolation_audit_parser_builds_and_parses_subcommands(monkeypatch):
    """main() builds the argparse parser and dispatches; with the two _cmd_* handlers
    spied, a known argv for each subcommand parses and routes correctly. No command
    body runs, so this is Docker-free and model-free."""
    seen = {}
    monkeypatch.setattr(
        isolation_audit, "_cmd_loop", lambda args: seen.update(loop=args)
    )
    monkeypatch.setattr(
        isolation_audit, "_cmd_benchmark", lambda args: seen.update(bench=args)
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "isolation_audit.py",
            "loop",
            "merge_intervals",
            "--cap",
            "3",
            "--plateau",
            "1",
        ],
    )
    isolation_audit.main()
    assert seen["loop"].cmd == "loop"
    assert seen["loop"].case == "merge_intervals"
    assert seen["loop"].cap == 3
    assert seen["loop"].plateau == 1

    seen.clear()
    monkeypatch.setattr(
        sys,
        "argv",
        ["isolation_audit.py", "benchmark", "--cap", "4", "--cases", "a", "b"],
    )
    isolation_audit.main()
    assert seen["bench"].cmd == "benchmark"
    assert seen["bench"].cap == 4
    assert seen["bench"].cases == ["a", "b"]


# --- bakeoff / verify_boundary / smoke_test: import-plus-callable guards -----
@pytest.mark.parametrize(
    "module_name",
    ["darwin.bakeoff", "darwin.verify_boundary", "darwin.smoke_test"],
)
def test_harness_imports_and_exposes_callable_main(module_name):
    """bakeoff, verify_boundary, and smoke_test each import cleanly and expose a
    callable main(). LIMIT, stated honestly: these harnesses do real work (Docker
    spin-ups, or seed-case evaluation through the real sandbox), so this guard is
    import-plus-callable ONLY -- it does NOT run main(). It catches an import-time or
    signature break, not a logic regression."""
    module = importlib.import_module(module_name)
    main = getattr(module, "main", None)
    assert callable(main), f"{module_name}.main is not callable"
