"""A minimal OS-level code sandbox: run a command against a set of files in an
isolated temp dir, under a hard wall-clock timeout, and report what happened.

This is the safety primitive shared by verify_case.py and (later) the evaluator.
It runs untrusted, LLM-generated code. The guarantee it must never break: a
runaway candidate (e.g. `while True: pass`) is killed at the timeout and the call
returns promptly — it must NEVER hang waiting on a runaway child. The command is
launched in a new session (its own process group); on timeout the group is
SIGKILLed and, best-effort, so is every descendant that broke away into its own
session. Output is then collected with a bounded read, so a breakaway child that
keeps the stdout pipe open can never wedge the call (see run()).

Best-effort, not bulletproof: a determined hostile candidate can still escape the
tree-kill (fast re-parenting, fork bombs, daemonization). Real containment needs
OS-level isolation (Docker / namespaces / cgroups) — the project's stated v2. The
mandatory, fully-honoured guarantee is the one above: always return, always clean
up the temp dir.

Generic on purpose: it runs a command and reports status / exit / output /
duration. It knows nothing about "tests" or "golden I/O"; that lives one layer up.

v1 isolation = subprocess in a fresh temp dir. Memory limits, network isolation,
and Docker-level isolation are explicitly v2 and NOT implemented here. (Unix only:
the process-group kill relies on setsid + killpg.)
"""

import os
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

# The four-way outcome. `crashed` means terminated by an OS signal (segfault,
# abort, ...). A Python-level exception is an ordinary non-zero exit and so lands
# in `failed`, with its traceback captured in stderr — the generic layer cannot
# tell a raised exception from a deliberate non-zero exit (see assumption #3).
OK = "ok"  # completed successfully (exit 0)
FAILED = "failed"  # completed with a non-zero exit code
CRASHED = "crashed"  # terminated abnormally by a signal
TIMED_OUT = "timed_out"  # killed by the sandbox's wall-clock timeout

# After a timeout kill, how long to wait for the pipe to drain before giving up.
# A breakaway child holding the pipe open can never block us longer than this.
_KILL_GRACE = 2.0


@dataclass
class SandboxResult:
    status: str  # one of OK / FAILED / CRASHED / TIMED_OUT
    exit_code: int | None  # process returncode; None when timed out
    stdout: str  # captured standard output
    stderr: str  # captured standard error
    duration: float  # wall-clock seconds the command actually ran
    timed_out: bool  # convenience flag, == (status == TIMED_OUT)


def run(files, command, timeout=10.0):
    """Write `files` (name -> text) into a fresh temp dir, run `command` there in
    its own process group, and return a SandboxResult. Enforces a hard `timeout`
    in seconds: on expiry the process group and its descendants are killed
    (best-effort) and the result is marked timed out. The call always returns
    within ~timeout (+ a bounded grace) and the temp dir is always removed before
    returning, even if a breakaway child keeps the output pipe open.
    """
    workdir = Path(tempfile.mkdtemp(prefix="sandbox_"))
    try:
        for name, content in files.items():
            path = workdir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        start = time.monotonic()
        proc = subprocess.Popen(
            command,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,  # own session/group -> whole tree killable
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc.pid)  # group + best-effort breakaway descendants
            try:
                # Bounded read. If a breakaway child still holds the pipe open,
                # this raises after _KILL_GRACE instead of blocking forever.
                # (Retrying communicate after a timeout does not lose output.)
                stdout, stderr = proc.communicate(timeout=_KILL_GRACE)
            except subprocess.TimeoutExpired:
                proc.kill()  # SIGKILL the direct child...
                try:
                    proc.wait(timeout=_KILL_GRACE)  # ...and reap it (it is dead)
                except subprocess.TimeoutExpired:
                    pass
                stdout, stderr = "", ""  # give up on output; never block
            return SandboxResult(
                TIMED_OUT, None, stdout, stderr, time.monotonic() - start, True
            )

        duration = time.monotonic() - start
        rc = proc.returncode
        status = OK if rc == 0 else CRASHED if rc < 0 else FAILED
        return SandboxResult(status, rc, stdout, stderr, duration, False)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _kill_tree(pid):
    """Best-effort: SIGKILL `pid`'s process group AND every descendant, including
    children that left the group via setsid / start_new_session. Descendants are
    enumerated BEFORE the group is killed, so a child that re-parents to init the
    instant its parent dies is still in the list.

    Best-effort only: a determined hostile candidate can still escape (fast
    re-parenting, fork bombs, daemonization). OS-level isolation is the v2 answer.
    Tier 1 (the bounded read in run()) is what guarantees we always return.
    """
    descendants = _descendants(pid)
    _kill_group(pid)
    for child in descendants:
        try:
            os.kill(child, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _kill_group(pid):
    """SIGKILL the whole process group led by `pid` (created via start_new_session)."""
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _descendants(root):
    """All transitive child PIDs of `root`, from a `ps` pid->ppid snapshot. Uses
    no extra dependency; returns [] if `ps` is unavailable (Tier 1 still holds)."""
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid=,ppid="], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    kids = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            kids.setdefault(int(parts[1]), []).append(int(parts[0]))
    found, stack = [], [root]
    while stack:
        for c in kids.get(stack.pop(), []):
            found.append(c)
            stack.append(c)
    return found
