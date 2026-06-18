"""Tests for the structured-logging setup (tools/logsetup.py) and the P4.4 routing
guarantees. No API key, no Docker: logsetup is pure logging configuration, and the
orchestrator logging is exercised through a console buffer and a JSON file.

Covers:
- the console handler renders message-only on its stream (aligned blocks intact);
- the JSON handler emits one valid JSON object per record with the documented
  envelope plus the extra fields;
- level filtering: at a higher console level, DEBUG records do not reach the console
  (but the JSON handler still records them);
- logging does not alter a written machine artifact;
- importing a core-path module configures no global (root) logging and emits nothing.

  cd tools && python -m pytest test_logsetup.py -q -p no:cacheprovider
"""

import io
import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

import benchmark
import logsetup
import mbenchmark

TOOLS = Path(__file__).resolve().parent


def _reset_darwin():
    """Drop our handlers so each test configures from a clean slate."""
    root = logging.getLogger("darwin")
    for h in list(root.handlers):
        root.removeHandler(h)


# ------------------------------------------------- console handler


def test_console_is_message_only_no_prefix():
    _reset_darwin()
    buf = io.StringIO()
    logsetup.configure(level="INFO", console_stream=buf)
    log = logsetup.get_logger("demo")
    log.info("=" * 20)  # an aligned block line
    log.info("case=%s done", "sum_evens")
    # Exactly the messages, in order, no level/timestamp prefix.
    assert buf.getvalue() == ("=" * 20) + "\ncase=sum_evens done\n"


# ------------------------------------------------- JSON handler


def test_json_handler_one_object_per_record_with_fields(tmp_path):
    _reset_darwin()
    jp = tmp_path / "log.jsonl"
    logsetup.configure(level="INFO", json_path=str(jp), console_stream=io.StringIO())
    log = logsetup.get_logger("benchmark")
    log.info(
        "case=%s done",
        "sum_evens",
        extra={
            "model": "claude-opus-4-8",
            "total_cost_usd": 0.012,
            "verdict": "improved (best candidate returned)",
            "total_input_tokens": 1000,
            "total_output_tokens": 2000,
        },
    )
    lines = jp.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])  # one valid JSON object per record
    # Envelope.
    for key in ("timestamp", "level", "logger", "message"):
        assert key in rec
    assert rec["level"] == "INFO"
    assert rec["logger"] == "darwin.benchmark"
    assert rec["message"] == "case=sum_evens done"
    # Documented run fields, serialized as top-level fields.
    assert rec["model"] == "claude-opus-4-8"
    assert rec["total_cost_usd"] == 0.012
    assert rec["verdict"] == "improved (best candidate returned)"
    assert rec["total_input_tokens"] == 1000 and rec["total_output_tokens"] == 2000


def test_json_handler_only_when_path_given():
    _reset_darwin()
    logsetup.configure(level="INFO", console_stream=io.StringIO())  # no json_path
    handlers = logging.getLogger("darwin").handlers
    assert len(handlers) == 1  # console only
    assert isinstance(handlers[0], logging.StreamHandler)


# ------------------------------------------------- level filtering


def test_level_filtering_suppresses_debug_on_console(tmp_path):
    _reset_darwin()
    buf = io.StringIO()
    jp = tmp_path / "log.jsonl"
    logsetup.configure(level="INFO", json_path=str(jp), console_stream=buf)
    log = logsetup.get_logger("demo")
    log.debug("a debug diagnostic", extra={"x": 1})
    log.info("an info line")
    console = buf.getvalue()
    assert (
        "a debug diagnostic" not in console
    )  # DEBUG filtered from the console at INFO
    assert "an info line" in console
    # The JSON handler still records the DEBUG line at full fidelity.
    levels = [
        json.loads(line)["level"]
        for line in jp.read_text(encoding="utf-8").splitlines()
    ]
    assert "DEBUG" in levels and "INFO" in levels


def test_higher_console_level_suppresses_info(tmp_path):
    _reset_darwin()
    buf = io.StringIO()
    logsetup.configure(level="WARNING", console_stream=buf)
    log = logsetup.get_logger("demo")
    log.info("info should be hidden")
    log.warning("warning should show")
    out = buf.getvalue()
    assert "info should be hidden" not in out
    assert "warning should show" in out


# ------------------------------------------------- machine artifact unchanged


@pytest.mark.parametrize(
    "module, name",
    [
        (benchmark, "aggregate.json"),
        (mbenchmark, "maggregate.json"),
    ],
)
def test_logging_does_not_alter_written_artifact(tmp_path, module, name):
    agg = {
        "model": "m",
        "n_cases": 1,
        "cases": [{"case": "a", "total_cost_usd": 0.01}],
        "improved": 1,
    }
    # Without logging configured.
    _reset_darwin()
    plain_path = module.write_aggregate(agg, tmp_path / "plain")
    plain = plain_path.read_bytes()
    assert plain_path.name == name
    # Byte-identical to the prior inline write: json.dumps(agg, indent=2), utf-8, no
    # trailing newline. This pins the extraction to the exact pre-refactor bytes.
    assert plain == json.dumps(agg, indent=2).encode("utf-8")
    # With logging configured (console + JSON).
    logsetup.configure(
        level="INFO",
        json_path=str(tmp_path / "log.jsonl"),
        console_stream=io.StringIO(),
    )
    logged = module.write_aggregate(agg, tmp_path / "logged").read_bytes()
    assert plain == logged  # the artifact bytes are identical


# ------------------------------------------------- import is side-effect-free


def test_importing_core_path_module_is_side_effect_free():
    script = (
        "import sys; sys.path.insert(0, '.'); import io, logging; "
        "root_before = list(logging.getLogger().handlers); "
        "import benchmark, mbenchmark, loop, mloop, evaluator, mevaluator, mverify, mgenerator; "
        "assert logging.getLogger().handlers == root_before, 'import configured root logging'; "
        "print('side-effect-free')"
    )
    r = subprocess.run(
        [sys.executable, "-c", script], cwd=str(TOOLS), capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "side-effect-free"
    assert r.stderr == ""  # nothing emitted on import


def test_get_logger_does_not_add_root_handlers():
    root_before = list(logging.getLogger().handlers)
    logsetup.get_logger("loop")  # lookup only, no configuration
    assert logging.getLogger().handlers == root_before
