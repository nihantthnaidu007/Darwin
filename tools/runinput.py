"""Guarded loading and shape validation for run-path JSON inputs (P4.5a).

The case, mcase, baseline, and aggregate readers on the run path used to call
json.loads / json.load with no guard and then index keys that might be absent, so a
missing or malformed input file ended a run with a raw JSONDecodeError,
FileNotFoundError, or a downstream KeyError instead of a message a human can act on.
This module is the ONE place that owns guarded loading and the case/mcase
required-key sets; the readers call it and never re-implement the guard.

  - load_json(path, what): read and parse a JSON file, raising RunInputError that
    names the file and the problem if it is missing, unreadable, or not valid JSON
    (never a raw FileNotFoundError, OSError, or JSONDecodeError). It uses
    Path.read_text, so no bare open() remains at the call sites.
  - load_case_meta(case_dir): load a single-function case meta.json, then require
    case_id and entry_point BEFORE the run uses them.
  - load_mcase_meta(case_dir): load a multi-file mcase meta.json, then require
    case_id and entry BEFORE the run uses them.

The required-key sets are exactly the keys the generators and verifiers index
without a default: entry_point for a case, entry for an mcase, plus case_id. Every
other key a reader touches (category, difficulty, kind, public_api,
stateful_because, constraints, description) is accessed with a default and stays
optional, so a valid existing case or mcase loads unchanged.
"""
import json
from pathlib import Path

# The required keys are exactly those the readers index WITHOUT a default; every
# other key stays optional so a valid existing case or mcase loads unchanged.
CASE_REQUIRED_KEYS = ("case_id", "entry_point")
MCASE_REQUIRED_KEYS = ("case_id", "entry")


class RunInputError(Exception):
    """A run-path input file is missing, unreadable, malformed, or missing a
    required key. Its message names the file and the problem, so a run that hits a
    bad input fails with something a human can act on, not a raw traceback."""


def load_json(path, what=None):
    """Read and parse `path` as JSON, guarded.

    Returns the parsed value. Raises RunInputError -- naming `path` and the problem
    -- if the file is missing, unreadable, or not syntactically valid JSON, instead
    of a raw FileNotFoundError, OSError, or JSONDecodeError. `what` is a short label
    for the kind of file (e.g. "case meta.json") that opens the message; it defaults
    to the file name, so a call site need not hand-pass a label that could desync
    from the real filename.
    """
    path = Path(path)
    if what is None:
        what = path.name
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise RunInputError(f"{what} not found: {path}") from None
    except OSError as e:
        raise RunInputError(f"{what} could not be read: {path} ({e})") from e
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RunInputError(
            f"{what} is not valid JSON: {path} "
            f"(line {e.lineno} column {e.colno}: {e.msg})"
        ) from e


def _load_meta(case_dir, required, what):
    """Load meta.json from `case_dir`, guarded, then require every key in
    `required`. Raises RunInputError naming the file and any missing key BEFORE the
    run uses the metadata, rather than a downstream KeyError."""
    path = Path(case_dir) / "meta.json"
    meta = load_json(path, what)
    if not isinstance(meta, dict):
        raise RunInputError(f"{what} must be a JSON object: {path}")
    missing = [k for k in required if k not in meta]
    if missing:
        keys = ", ".join(repr(k) for k in missing)
        raise RunInputError(f"{what} is missing required key(s) {keys}: {path}")
    return meta


def load_case_meta(case_dir):
    """Single-function case meta.json: guarded load + require case_id, entry_point."""
    return _load_meta(case_dir, CASE_REQUIRED_KEYS, "case meta.json")


def load_mcase_meta(case_dir):
    """Multi-file mcase meta.json: guarded load + require case_id, entry."""
    return _load_meta(case_dir, MCASE_REQUIRED_KEYS, "mcase meta.json")
