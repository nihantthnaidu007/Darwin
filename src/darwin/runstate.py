"""Shared run-state checkpointing for the multi-case benchmarks (P4.2, P4.2.2).

Both src/darwin/benchmark.py and src/darwin/mbenchmark.py run the loop once per case and
then aggregate the per-case results. A crash mid-corpus used to discard every
completed case. This module persists each case result the moment it completes, so
an interrupted run can resume from the first incomplete case. It is the ONE place
that owns the format, the write, the read, the completed-case detection, AND the
run-configuration record plus the fail-closed mismatch check on resume; the
orchestrators call it and never re-implement any of it.

Format: append-only JSONL under runs/ (already gitignored). The first record is the
run configuration written by the fresh run; the rest are one record per completed
case:

    {"config": {"model": "<id>", "cap": <int>, "plateau": <int>}}
    {"case": "<case id>", "result": <the per-case summary the aggregate is built from>}
    ...

Human-readable, append-friendly, and crash-tolerant by construction. json.dumps
emits no literal newline (newlines inside strings are escaped as \\n), so the only
raw newline byte is our record terminator. A record is therefore complete iff its
line ends in "\\n"; a crash mid-write leaves a trailing line with no terminator,
which the reader treats as not-yet-complete so that case is re-run. A later record
for the same case wins (last write), so re-running a case after a partial write is
safe. See docs/decisions/0017-run-state-checkpointing.md.

Resume is fail-closed on configuration: a fresh run records the config (model, cap,
plateau), and resume refuses with a clear error if the current invocation differs
from the recorded one, rather than mix two configs into one aggregate labeled with
only the new config. Resume also assumes the SAME corpus; after the corpus changes,
start a fresh run (the default), not a resume.
"""

import json
import os
from pathlib import Path


class ConfigMismatchError(Exception):
    """Raised when --resume is invoked with a run configuration that differs from
    the one that produced the saved run-state. The run fails closed instead of
    silently mixing results from two configurations into one aggregate."""

    def __init__(self, diffs):
        self.diffs = diffs  # {field: (saved_value, current_value)}
        fields = ", ".join(
            f"{k} (saved {saved!r}, now {current!r})"
            for k, (saved, current) in sorted(diffs.items())
        )
        super().__init__(
            f"resume refused: the run configuration does not match the saved "
            f"run-state -- {fields}. Re-run with the original configuration to "
            f"resume, or start a fresh run (omit --resume) to overwrite the saved "
            f"state with this configuration."
        )


def run_config(model, cap, plateau):
    """The canonical run-configuration record persisted in run-state and compared
    on resume. Defined once here so the two orchestrators cannot drift on field
    names; they pass the result to RunState.start() / RunState.resume()."""
    return {"model": model, "cap": cap, "plateau": plateau}


class RunState:
    """An append-only JSONL checkpoint of the run config + completed cases at `path`."""

    def __init__(self, path):
        self.path = Path(path)

    def clear(self):
        """Drop any prior state so a fresh run never inherits stale records or a
        stale config. (start() calls this before recording the new config.)"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()

    def _append_line(self, record):
        """Append one JSONL record, flushed and fsynced, so everything already
        written survives an interrupted run."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True) + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def start(self, config):
        """Begin a FRESH run: drop any prior state, then record `config` as the
        first record so a later resume can verify it matches. Overwriting prior
        state is what makes a fresh run never silently skip cases (or inherit a
        config) from a stale previous run."""
        self.clear()
        self._append_line({"config": config})

    def append(self, case, result):
        """Persist one completed case immediately."""
        self._append_line({"case": case, "result": result})

    def read_config(self):
        """The run configuration recorded by start(), or None if the state has no
        config record yet (no prior fresh run, or an empty/torn file)."""
        return self._scan(want_config=True)

    def completed(self):
        """Map case id -> persisted result for every COMPLETE case record, in order.

        The leading config record is skipped (it is not a case). A partial trailing
        record (a crash mid-write, recognizable as a final line with no "\\n"
        terminator, or any line that fails to parse) is ignored, so that case is
        treated as not done and gets re-run. A later record for the same case
        overwrites an earlier one (last write wins).
        """
        return self._scan(want_config=False)

    def _scan(self, want_config):
        """One reader for both views. Walks complete records (stopping at the first
        partial/torn line); returns the first config record when want_config, else
        the case-id -> result map."""
        out = {}
        if not self.path.exists():
            return None if want_config else out
        with open(self.path, "r", encoding="utf-8") as f:
            for raw in f:
                if not raw.endswith("\n"):
                    break  # partial trailing record: no terminator -> incomplete
                line = raw.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    break  # defensive: a torn record -> treat the rest as not done
                if "config" in rec:
                    if want_config:
                        return rec["config"]
                    continue  # skip the header when collecting completed cases
                if not want_config and "case" in rec:
                    out[rec["case"]] = rec["result"]
        return None if want_config else out

    def resume(self, config):
        """Resume an interrupted run. Verify the recorded run configuration matches
        `config` and FAIL CLOSED on any mismatch (raise ConfigMismatchError) rather
        than mix two configs into one aggregate. Returns the completed-case map. If
        there is no recorded config (no prior fresh run), there is nothing to
        verify and the completed map is whatever is on disk."""
        recorded = self.read_config()
        if recorded is not None:
            diffs = {
                k: (recorded.get(k), config[k])
                for k in config
                if recorded.get(k) != config[k]
            }
            if diffs:
                raise ConfigMismatchError(diffs)
        return self.completed()
