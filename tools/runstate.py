"""Shared run-state checkpointing for the multi-case benchmarks (P4.2).

Both tools/benchmark.py and tools/mbenchmark.py run the loop once per case and
then aggregate the per-case results. A crash mid-corpus used to discard every
completed case. This module persists each case result the moment it completes, so
an interrupted run can resume from the first incomplete case. It is the ONE place
that owns the format, the write, the read, and the completed-case detection; the
orchestrators call it and never re-implement it.

Format: append-only JSONL under runs/ (already gitignored), one record per
completed case:

    {"case": "<case id>", "result": <the per-case summary the aggregate is built from>}

Human-readable, append-friendly, and crash-tolerant by construction. json.dumps
emits no literal newline (newlines inside strings are escaped as \\n), so the only
raw newline byte is our record terminator. A record is therefore complete iff its
line ends in "\\n"; a crash mid-write leaves a trailing line with no terminator,
which the reader treats as not-yet-complete so that case is re-run. A later record
for the same case wins (last write), so re-running a case after a partial write is
safe. See docs/decisions/0017-run-state-checkpointing.md.

Resume assumes the SAME corpus and config. After the corpus changes, start a fresh
run (the default), not a resume; a fresh run clears prior state first.
"""
import json
import os
from pathlib import Path


class RunState:
    """An append-only JSONL checkpoint of completed cases at `path`."""

    def __init__(self, path):
        self.path = Path(path)

    def clear(self):
        """Start a fresh run clean: drop any prior state so a fresh run never
        silently skips cases left over from a stale previous run."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()

    def append(self, case, result):
        """Persist one completed case immediately. Append-only, then flushed and
        fsynced so everything already written survives an interrupted run."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"case": case, "result": result}, sort_keys=True) + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def completed(self):
        """Map case id -> persisted result for every COMPLETE record in order.

        A partial trailing record (a crash mid-write, recognizable as a final line
        with no "\\n" terminator, or any line that fails to parse) is ignored, so
        that case is treated as not done and gets re-run. A later record for the
        same case overwrites an earlier one (last write wins).
        """
        out = {}
        if not self.path.exists():
            return out
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
                out[rec["case"]] = rec["result"]
        return out
