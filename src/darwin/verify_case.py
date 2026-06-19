"""The gatekeeper. A candidate passes ONLY if its test suite passes AND it
reproduces every golden I/O pair exactly. Either alone is insufficient.

The candidate is untrusted LLM output, so BOTH checks run inside the I0 container
(sandbox_container.py): the test suite and the golden-I/O replay each execute in a
locked-down container (no network, no host filesystem, memory/CPU/PID caps, non-root,
hard timeout), never imported into this (parent/host) process.

Information flow for the golden replay (the container is the boundary): the container
receives the candidate and the golden INPUTS only — never the expected OUTPUTS. The
in-container driver calls the entry point and emits the actual results; this HOST
process holds the expected outputs and does the comparison. The golden outputs are
never placed in the container and the comparison never happens inside it.

THREAT MODEL / BOUNDARY (v2 / Phase I1) — read this before trusting the behavior gate.
The boundary is the container, not a process group. The container walls off ACCESS
(host filesystem, network, the golden oracle); it does NOT split the process, so the
candidate and the trusted emitter are still CO-RESIDENT (`import candidate` runs
untrusted code in the emitter's process, now inside the container). In-process
interposition therefore remains possible. Do NOT describe this gate as "forgery-proof".

CLOSED by the container boundary (access cut off):
  - ORACLE-READ: a candidate that reads the golden answer key off disk and echoes it.
    Closed: the container has no host filesystem access (read-only root; only the per-run
    dir is mounted, holding candidate + inputs only), so the golden file is unreachable.
    The candidate finds nothing -> its entry point returns wrong -> behavior-mismatch.
  - HOST FILESYSTEM / SECRET ACCESS and NETWORK ACCESS: closed by the container lockdown.
  - The LITERAL `import __main__; __main__._dumps = <forged>` (or `__main__._write`)
    syntactic hijack: closed by local-capture. The driver body runs inside _run(), so
    _write/_dumps/_fd are frame-locals, not __main__ module attributes; that literal form
    writes a module attribute the trusted frame never reads. (Bounding the LITERAL form
    only; see the OPEN item below — this is NOT a general close of serializer hijacking.)

OPEN in-process — NOT closable at this layer, do NOT claim closed:
  - TRUSTED-CODE / SERIALIZER HIJACK (frame-locals write-through). DEMONSTRATED on
    Python 3.13: a candidate walks the stack frames (sys._getframe().f_back) to the
    driver frame, finds the trusted _dumps LOCAL, and overwrites it via the PEP 667
    write-through f_locals proxy with a lambda returning a HARDCODED correct answer. The
    driver then emits the forged-correct frame and a behavior-wrong candidate is SCORED.
    Local-capture does NOT stop this: a frame-local is reachable by frame-walking. This
    is the general form of the hijack the literal `import __main__` line was only one
    instance of. It is pinned as a known-open bypass in test_behavior_gate_limits.py.
  - COMPUTE-AND-LIE: a candidate that computes the correct outputs from the inputs (the
    inputs are necessarily in the container) and emits them while its declared entry
    point is wrong. The container cannot distinguish a correct emission produced by the
    real entry point from one produced by other in-process code.
  Both stem from the candidate and the trusted emitter sharing a process; the in-process
  interposition surface is fundamentally unbounded (the v1 audits stand), so NO in-process
  scheme closes it. The real fix is an ARCHITECTURE change — split the trusted emitter out
  of the candidate's process — deferred to a dedicated decision, NOT patched here.
  NOTE on disincentive: the earlier argument that "forging requires adding real
  computation, so it worsens the score the optimizer minimizes" is REFUTED for the
  hijack — the demonstrated frame-locals hijack forges with a HARDCODED constant plus a
  trivial, problem-independent frame walk: low complexity, NOT optimizer-disincentivized.
  At most, that argument applies to genuine compute-and-lie (which does add computation);
  it does NOT cover a hardcoded trusted-helper hijack.

Usage: python verify_case.py <candidate.py> <test_suite.py> <golden_io.json>
Prints "PASS" or "FAIL: <reason>" and exits 0 (pass) / 1 (fail).

Two entry points:
  classify(...) -> VerifyResult  — structured outcome with the Phase 1 taxonomy
                                   (tests-failed / could-not-run / crashed /
                                   timed-out / behavior-mismatch). The evaluator's
                                   Layer 1 + Layer 2 gates consume this.
  verify(...)   -> (ok, reason)  — the original boolean contract, kept intact for
                                   build_case.py; now a thin wrapper over classify.
The two container runs live here only; nothing downstream re-runs them.

PREREQUISITE (Phase I1): Docker must be running and the sandbox image built once
(docker build -f docker/Dockerfile.sandbox -t darwin-sandbox:py313 docker/); the
container run() raises RuntimeError with that hint if the image is missing.
"""

import json
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

# Phase I1: the candidate now runs behind the I0 container boundary, not the v1
# subprocess sandbox. sandbox_container exposes the SAME contract (run(); the
# OK/FAILED/CRASHED/TIMED_OUT taxonomy; a result with status/exit_code/stdout/
# stderr/duration/timed_out), so the gate logic below is unchanged — only WHERE
# the candidate executes moved across the OS boundary. Aliased to `sandbox` so the
# two run-sites and the status checks read identically to v1.
from darwin import sandbox_container as sandbox


# Rejection taxonomy (Phase 1). A passing candidate has code == None.
TESTS_FAILED = "tests-failed"  # pytest ran and an assertion failed (exit 1)
COULD_NOT_RUN = "could-not-run"  # syntax/import/collection error (exit != 0,1)
CRASHED = "crashed"  # killed by a signal mid-run
TIMED_OUT = "timed-out"  # hit the sandbox wall-clock timeout
BEHAVIOR_MISMATCH = "behavior-mismatch"  # tests pass but golden I/O diverges


@dataclass
class VerifyResult:
    ok: bool  # passed BOTH gates
    code: str | None  # None if ok; else one of the taxonomy constants above
    gate: str | None  # which gate decided it: "tests" / "golden" / None if ok
    reason: str  # human-readable detail (pytest output / mismatch / status)


# The trusted in-container golden driver. The candidate is untrusted code that this
# driver `import`s, so it runs in THE SAME process as this trusted emission. The
# container is the security boundary for ACCESS (no host FS -> closes oracle-read; see
# docstring), but it does NOT split the process, so in-process interposition stays open.
# The emission has these properties (they raise the bar for naive cheats; they do NOT
# make it forgery-proof, see the closing note):
#   1. bind os.write + json.dumps and LOAD the inputs BEFORE `import candidate`, so a
#      monkeypatched json (or tampered inputs) can't hijack what or how we emit;
#   2. emit the entry point's actual RETURN VALUES (objects), not candidate-printed text;
#   3. emit them with a single raw os.write to fd 1 (NOT the sys.stdout object the
#      candidate may have replaced), framed by a random per-run token;
#   4. os._exit(0) IMMEDIATELY — no atexit, __del__, thread, or buffered print the
#      candidate registered can run AFTER us to append or replace a result. (os._exit
#      also drops the candidate's own buffered stdout, so it can't even add noise via
#      print(); only a direct os.write at import could, which makes a 2nd frame -> the
#      parent fails closed below.)
#   5. (Phase I1) run the body INSIDE _run(), so _write/_dumps/_fd are frame-locals, not
#      __main__ module attributes. This closes ONLY the LITERAL
#      `import __main__; __main__._dumps = <forged>` form (it would set a module attribute
#      the trusted frame never reads). It does NOT close serializer hijacking in general.
# The HOST holds the expected outputs and compares there; the container never sees them.
# OPEN, NOT closed (do not claim otherwise): the TRUSTED-CODE / SERIALIZER HIJACK in its
# general form. On Python 3.13 a candidate can walk stack frames to this frame and
# overwrite the _dumps LOCAL via the PEP 667 write-through f_locals proxy (with a
# HARDCODED answer), forging a passing frame for a behavior-wrong entry point. So can
# COMPUTE-AND-LIE. Both follow from the candidate and emitter sharing a process; the
# interposition surface is unbounded (the v1 audits stand). Closing them needs a process
# split (architecture change), not a patch. See test_behavior_gate_limits.py for the
# pinned, known-open bypasses.
def _golden_driver(token):
    # Body lives in _run() so the trusted helpers are frame-locals. This closes ONLY the
    # literal `import __main__; __main__._dumps = ...` form (which sets a module attribute);
    # it does NOT stop a frame-walk that overwrites the _dumps local (PEP 667), which is
    # an OPEN bypass — see test_behavior_gate_limits.py. Not a general anti-hijack defense.
    return (
        "import json, os\n"
        "def _run():\n"
        # Keep a PRIVATE dup of the result pipe taken BEFORE the untrusted import, so a
        # candidate that redirects fd 1 (dup2 /dev/null over stdout) cannot suppress our
        # frame — at worst it adds a second one, which the parent rejects (fail closed).
        "    _write, _dumps, _fd = os.write, json.dumps, os.dup(1)\n"
        "    inputs = json.load(open('inputs.json', encoding='utf-8'))\n"
        "    import candidate\n"
        "    fn = getattr(candidate, inputs['entry_point'])\n"
        # json.dumps (pre-bound) does the tuple->list normalization golden relies on.
        "    results = [fn(*c['args'], **c['kwargs']) for c in inputs['cases']]\n"
        "    _write(_fd, ('\\n' + "
        + repr(token)
        + " + _dumps({'results': results}) + '\\n').encode())\n"
        "    os._exit(0)\n"
        "_run()\n"
    )


def _extract_results(stdout, token):
    """Read the trusted driver's result frame. Fail CLOSED unless EXACTLY ONE
    token-prefixed line is present: zero means the candidate suppressed/never wrote
    it, two-or-more means it injected a forged frame ALONGSIDE the real one — either
    way we cannot trust the result, so we reject. This catches the add-a-second-frame
    cheats (a direct os.write at import; atexit/sys.stdout tricks no longer work against
    raw-fd-write + os._exit). It does NOT catch a hijack that forges the SINGLE
    legitimate frame in place — e.g. overwriting the driver's _dumps local via a
    frame-walk (PEP 667) emits exactly one (forged) frame and passes this check. That
    is an OPEN bypass; see the module docstring and test_behavior_gate_limits.py."""
    frames = [
        line[len(token) :] for line in stdout.splitlines() if line.startswith(token)
    ]
    if len(frames) != 1:
        return None
    try:
        return json.loads(frames[0])["results"]
    except (ValueError, KeyError, TypeError):
        return None


def _classify_run(res, mismatch_code):
    """Map a container result to a taxonomy code. The container stays test-agnostic, so
    a broken-on-import candidate arrives here as `failed` (non-zero exit), same as a
    real assertion/mismatch. Knowing the program, we reconcile: exit 1 means it ran
    and produced a wrong answer (tests failed / golden mismatch); anything else
    non-OK means it could not even run that to completion."""
    if res.status == sandbox.TIMED_OUT:
        return TIMED_OUT
    if res.status == sandbox.CRASHED:
        return CRASHED
    if res.exit_code == 1:
        return mismatch_code
    return COULD_NOT_RUN


_LABEL = {
    TESTS_FAILED: "tests failed",
    COULD_NOT_RUN: "candidate could not run",
    CRASHED: "candidate crashed",
    TIMED_OUT: "candidate timed out",
}


def classify(candidate_path, test_suite_path, golden_path, timeout=10.0):
    """Run the two gates in order and return a structured VerifyResult. Layer 1
    (pytest) before Layer 2 (golden replay); the first failing gate decides."""
    candidate_src = Path(candidate_path).read_text(encoding="utf-8")
    test_src = Path(test_suite_path).read_text(encoding="utf-8")
    golden_src = Path(golden_path).read_text(encoding="utf-8")

    # Accepted residual: test_suite.py is readable by the candidate here (pytest
    # needs the file present, and it goes INTO the container with the candidate), so a
    # candidate could memorize the exact test inputs' outputs. Layer 2's golden replay
    # catches such a memorizer whenever the golden set contains inputs the suite lacks
    # (e.g. sum_evens' golden has a length-20 list no test uses). Phase-0 mitigation:
    # build cases so each golden input set is NOT a subset of its test inputs. The
    # candidate seeing its own tests is accepted, as in v1.
    # The container's python (not the host sys.executable, which does not exist inside
    # the image) runs pytest; -p no:cacheprovider avoids a .pytest_cache write against
    # the read-only root filesystem. Pass/fail semantics are unchanged.
    pytest_res = sandbox.run(
        {"candidate.py": candidate_src, "test_suite.py": test_src},
        ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_suite.py"],
        timeout,
    )
    if pytest_res.status != sandbox.OK:
        code = _classify_run(pytest_res, TESTS_FAILED)
        detail = pytest_res.stdout + pytest_res.stderr
        return VerifyResult(False, code, "tests", f"pytest: {_LABEL[code]}:\n" + detail)

    # Layer 2 (golden replay). Send the candidate the INPUTS only; keep the expected
    # outputs here on the HOST. The in-container driver emits actual results; we compare.
    golden = json.loads(golden_src)
    token = secrets.token_hex(16)
    inputs = {
        "entry_point": golden["entry_point"],
        "cases": [{"args": c["args"], "kwargs": c["kwargs"]} for c in golden["cases"]],
    }
    golden_res = sandbox.run(
        {
            "candidate.py": candidate_src,
            "inputs.json": json.dumps(inputs),
            "driver.py": _golden_driver(token),
        },
        ["python", "driver.py"],
        timeout,
    )
    if golden_res.status != sandbox.OK:
        code = _classify_run(golden_res, BEHAVIOR_MISMATCH)
        reason = (
            golden_res.stdout.strip()
            or golden_res.stderr.strip()
            or f"golden replay {golden_res.status}"
        )
        return VerifyResult(False, code, "golden", reason)

    # Driver exited 0: compare the actual results (held nowhere but here) to golden.
    actuals = _extract_results(golden_res.stdout, token)
    if actuals is None or len(actuals) != len(golden["cases"]):
        # No verifiable results: candidate suppressed/corrupted the driver's output.
        # Fail closed — a replay we cannot verify is not a pass.
        return VerifyResult(
            False,
            COULD_NOT_RUN,
            "golden",
            "golden replay produced no verifiable results "
            "(candidate may have suppressed or corrupted driver output)",
        )
    for case, actual in zip(golden["cases"], actuals):
        if actual != case["output"]:
            return VerifyResult(
                False,
                BEHAVIOR_MISMATCH,
                "golden",
                "golden mismatch for args=%s kwargs=%s: expected %r, got %r"
                % (case["args"], case["kwargs"], case["output"], actual),
            )

    return VerifyResult(True, None, None, "pytest passed and all golden I/O matched")


def verify(candidate_path, test_suite_path, golden_path, timeout=10.0):
    """Boolean contract kept for build_case.py: (ok, reason)."""
    r = classify(candidate_path, test_suite_path, golden_path, timeout)
    return r.ok, r.reason


def main():
    if len(sys.argv) != 4:
        sys.exit(
            "usage: python verify_case.py <candidate.py> <test_suite.py> "
            "<golden_io.json>"
        )
    ok, reason = verify(*sys.argv[1:4])
    print("PASS" if ok else "FAIL: " + reason)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
