"""Structured logging setup for Darwin's core path (P4.4).

ONE place that configures the project's logger, used by the core-path modules
(loop, mloop, generator, mgenerator, evaluator, mevaluator, mverify, benchmark,
mbenchmark) so none of them duplicate logging configuration. Two handlers:

  * a human-readable CONSOLE handler on stderr that renders only the message (no
    level or timestamp prefix), so the existing aligned progress blocks and tables
    print exactly as before, just on stderr instead of stdout. Its level is
    configurable (default INFO) and is the one that filters interactive output.
  * an optional structured JSON handler that emits one valid JSON object per
    record -- timestamp, level, logger name, message, and any fields attached via
    the logging `extra=` mechanism -- so unattended runs are machine-parseable.

Separation of streams (so the two can be captured apart):
  * stdout carries the program's RESULT -- the RUN SUMMARY report printed by
    run_summary / mrun_summary (left on print()).
  * stderr carries the operational LOG emitted here.

Configuration happens only at the entry points via configure(); importing this
module (or any core-path module) configures no global logging and emits nothing.
A NullHandler on the "darwin" logger keeps it silent until configure() runs, and
the "darwin" namespace is isolated from the root logger (propagate=False), so we
never touch global/root logging.

Environment:
  DARWIN_LOG_LEVEL  console level (DEBUG/INFO/WARNING/ERROR; default INFO)
  DARWIN_LOG_JSON   path for the JSON handler; when unset, console only

The documented structured field names are in docs/decisions/0018-structured-logging.md.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

_NAMESPACE = "darwin"

# Standard LogRecord attributes; anything else on a record came from `extra=` and
# is serialized by the JSON handler as a structured field.
_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as one line of JSON: timestamp, level, logger, message,
    plus every field attached via `extra=`."""

    def format(self, record):
        obj = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                obj[key] = value
        if record.exc_info:
            obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(obj, default=str)


def get_logger(name):
    """A core-path module logger under the isolated "darwin" namespace. This only
    looks the logger up; it never configures handlers or emits output, so calling
    it at module import is side-effect-free."""
    return logging.getLogger(f"{_NAMESPACE}.{name}")


def configure(level=None, json_path=None, console_stream=None):
    """Wire the "darwin" logger's handlers. Call once at an entry point (main()),
    never at import time. Idempotent: repeated calls replace our handlers rather
    than stacking them.

    level         console level; falls back to DARWIN_LOG_LEVEL, then INFO.
    json_path     JSON handler destination; falls back to DARWIN_LOG_JSON. When
                  neither is set, only the console handler is installed.
    console_stream  override the console stream (default sys.stderr); for tests.
    """
    level_name = (level or os.environ.get("DARWIN_LOG_LEVEL") or "INFO").upper()
    console_level = getattr(logging, level_name, logging.INFO)
    json_path = json_path or os.environ.get("DARWIN_LOG_JSON")

    root = logging.getLogger(_NAMESPACE)
    root.setLevel(logging.DEBUG)  # the handlers do the filtering
    root.propagate = False  # isolated from the root/global logger
    for handler in list(root.handlers):  # drop prior handlers (incl. the NullHandler)
        root.removeHandler(handler)

    console = logging.StreamHandler(console_stream or sys.stderr)
    console.setLevel(console_level)
    console.setFormatter(
        logging.Formatter("%(message)s")
    )  # no prefix: aligned blocks intact
    root.addHandler(console)

    if json_path:
        jh = logging.FileHandler(json_path, encoding="utf-8")
        jh.setLevel(logging.DEBUG)  # the JSON record is the full-fidelity stream
        jh.setFormatter(JsonFormatter())
        root.addHandler(jh)

    return root


# Library-safe import: keep the "darwin" logger silent and isolated until an entry
# point calls configure(). This touches only our own namespace, never root, and
# emits nothing -- importing a core-path module configures no global logging.
_root = logging.getLogger(_NAMESPACE)
_root.addHandler(logging.NullHandler())
_root.propagate = False
