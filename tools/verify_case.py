"""The gatekeeper. A candidate passes ONLY if its test suite passes AND it
reproduces every golden I/O pair exactly. Either alone is insufficient.

The candidate is untrusted LLM output, so BOTH checks run inside the sandbox
(sandbox.py): the test suite and the golden-I/O replay are each executed in an
isolated temp dir under a hard timeout, never imported into this (parent) process.

Information flow for the golden replay: the sandbox receives the candidate and the
golden INPUTS only — never the expected OUTPUTS. The in-sandbox driver calls the
entry point and emits the actual results; this parent process holds the expected
outputs and does the comparison. So a candidate cannot simply READ its own answer key.

THREAT MODEL / BOUNDARY (v1) — read this before trusting the behavior gate:
  The driver runs in the SAME OS process as the untrusted candidate (Python `import`).
  That means trusted result-handling (the serializer, the write, the driver's globals)
  is co-resident with — and therefore reachable/replaceable by — candidate code. An
  ADVERSARIAL candidate can forge a passing result, e.g. a one-line
  `import __main__; __main__._dumps = <forged>` hijack, an fd-table rewrite, or a
  `sys.excepthook`-based exit. Three audits established this surface is unbounded:
  NO in-process scheme closes it. See test_behavior_gate_limits.py for live cheats.
  - The gate IS relied upon as robust against GOOD-FAITH candidates: output from an
    LLM trying to SIMPLIFY code. Forgery is self-defeating for that optimizer —
    every forgery shim ADDS complexity and worsens the very score being minimized.
  - The gate is NOT hardened against adversarial candidates. Closing that requires
    OS-LEVEL ISOLATION (containers / namespaces / seccomp), deferred to v2.
  Do NOT describe this gate as "forgery-proof." It is not, by design, in v1.

Usage: python verify_case.py <candidate.py> <test_suite.py> <golden_io.json>
Prints "PASS" or "FAIL: <reason>" and exits 0 (pass) / 1 (fail).

Two entry points:
  classify(...) -> VerifyResult  — structured outcome with the Phase 1 taxonomy
                                   (tests-failed / could-not-run / crashed /
                                   timed-out / behavior-mismatch). The evaluator's
                                   Layer 1 + Layer 2 gates consume this.
  verify(...)   -> (ok, reason)  — the original boolean contract, kept intact for
                                   build_case.py; now a thin wrapper over classify.
The two sandbox.run calls live here only; nothing downstream re-runs them.
"""
import json
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

import sandbox

# Rejection taxonomy (Phase 1). A passing candidate has code == None.
TESTS_FAILED = "tests-failed"            # pytest ran and an assertion failed (exit 1)
COULD_NOT_RUN = "could-not-run"          # syntax/import/collection error (exit != 0,1)
CRASHED = "crashed"                      # killed by a signal mid-run
TIMED_OUT = "timed-out"                  # hit the sandbox wall-clock timeout
BEHAVIOR_MISMATCH = "behavior-mismatch"  # tests pass but golden I/O diverges


@dataclass
class VerifyResult:
    ok: bool             # passed BOTH gates
    code: str | None     # None if ok; else one of the taxonomy constants above
    gate: str | None     # which gate decided it: "tests" / "golden" / None if ok
    reason: str          # human-readable detail (pytest output / mismatch / status)

# The trusted in-sandbox golden driver. The candidate is untrusted code running in
# THIS SAME process, so the two DEMONSTRATED stdout forgeries (atexit print after the
# driver; replacing sys.stdout to swallow the driver's line) are closed here:
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
# The parent holds the expected outputs and compares there; the sandbox never sees them.
# These defenses harden the gate against good-faith candidates and the demonstrated
# stdout vectors. They do NOT make it forgery-proof against an adversarial candidate
# (see the module docstring's THREAT MODEL / BOUNDARY note and test_behavior_gate_limits.py);
# that needs OS-level isolation (v2).
def _golden_driver(token):
    return (
        "import json, os\n"
        # Keep a PRIVATE dup of the result pipe taken BEFORE the untrusted import, so a
        # candidate that redirects fd 1 (dup2 /dev/null over stdout) cannot suppress our
        # frame — at worst it adds a second one, which the parent rejects (fail closed).
        "_write, _dumps, _fd = os.write, json.dumps, os.dup(1)\n"
        "inputs = json.load(open('inputs.json', encoding='utf-8'))\n"
        "import candidate\n"
        "fn = getattr(candidate, inputs['entry_point'])\n"
        # json.dumps (pre-bound) does the tuple->list normalization golden relies on.
        "results = [fn(*c['args'], **c['kwargs']) for c in inputs['cases']]\n"
        "_write(_fd, ('\\n' + " + repr(token) + " + _dumps({'results': results}) + '\\n').encode())\n"
        "os._exit(0)\n"
    )


def _extract_results(stdout, token):
    """Read the trusted driver's result frame. Fail CLOSED unless EXACTLY ONE
    token-prefixed line is present: zero means the candidate suppressed/never wrote
    it, two-or-more means it injected a forged frame alongside the real one — either
    way we cannot trust the result, so we reject. (Forging requires a direct os.write
    at import, which adds a second frame; replacing sys.stdout or scheduling atexit
    no longer works against raw-fd-write + os._exit.)"""
    frames = [line[len(token):] for line in stdout.splitlines() if line.startswith(token)]
    if len(frames) != 1:
        return None
    try:
        return json.loads(frames[0])["results"]
    except (ValueError, KeyError, TypeError):
        return None


def _classify_run(res, mismatch_code):
    """Map a SandboxResult to a taxonomy code. The sandbox stays test-agnostic, so
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
    TESTS_FAILED: "tests failed", COULD_NOT_RUN: "candidate could not run",
    CRASHED: "candidate crashed", TIMED_OUT: "candidate timed out",
}


def classify(candidate_path, test_suite_path, golden_path, timeout=10.0):
    """Run the two gates in order and return a structured VerifyResult. Layer 1
    (pytest) before Layer 2 (golden replay); the first failing gate decides."""
    candidate_src = Path(candidate_path).read_text(encoding="utf-8")
    test_src = Path(test_suite_path).read_text(encoding="utf-8")
    golden_src = Path(golden_path).read_text(encoding="utf-8")

    # Accepted v1 residual: test_suite.py is readable by the candidate here (pytest
    # needs the file present), so a candidate could memorize the exact test inputs'
    # outputs. Layer 2's golden replay catches such a memorizer whenever the golden
    # set contains inputs the suite lacks (e.g. sum_evens' golden has a length-20 list
    # no test uses). Phase-0 mitigation: build cases so each golden input set is NOT a
    # subset of its test inputs. Fully hiding the spec from the test runner needs
    # OS-level isolation (v2) and is out of scope for this gate.
    pytest_res = sandbox.run(
        {"candidate.py": candidate_src, "test_suite.py": test_src},
        [sys.executable, "-m", "pytest", "-q", "test_suite.py"],
        timeout,
    )
    if pytest_res.status != sandbox.OK:
        code = _classify_run(pytest_res, TESTS_FAILED)
        detail = pytest_res.stdout + pytest_res.stderr
        return VerifyResult(False, code, "tests",
                            f"pytest: {_LABEL[code]}:\n" + detail)

    # Layer 2 (golden replay). Send the candidate the INPUTS only; keep the expected
    # outputs here in the parent. The driver prints actual results; we compare.
    golden = json.loads(golden_src)
    token = secrets.token_hex(16)
    inputs = {"entry_point": golden["entry_point"],
              "cases": [{"args": c["args"], "kwargs": c["kwargs"]}
                        for c in golden["cases"]]}
    golden_res = sandbox.run(
        {"candidate.py": candidate_src,
         "inputs.json": json.dumps(inputs),
         "driver.py": _golden_driver(token)},
        [sys.executable, "driver.py"],
        timeout,
    )
    if golden_res.status != sandbox.OK:
        code = _classify_run(golden_res, BEHAVIOR_MISMATCH)
        reason = (golden_res.stdout.strip() or golden_res.stderr.strip()
                  or f"golden replay {golden_res.status}")
        return VerifyResult(False, code, "golden", reason)

    # Driver exited 0: compare the actual results (held nowhere but here) to golden.
    actuals = _extract_results(golden_res.stdout, token)
    if actuals is None or len(actuals) != len(golden["cases"]):
        # No verifiable results: candidate suppressed/corrupted the driver's output.
        # Fail closed — a replay we cannot verify is not a pass.
        return VerifyResult(False, COULD_NOT_RUN, "golden",
                            "golden replay produced no verifiable results "
                            "(candidate may have suppressed or corrupted driver output)")
    for case, actual in zip(golden["cases"], actuals):
        if actual != case["output"]:
            return VerifyResult(
                False, BEHAVIOR_MISMATCH, "golden",
                "golden mismatch for args=%s kwargs=%s: expected %r, got %r"
                % (case["args"], case["kwargs"], case["output"], actual))

    return VerifyResult(True, None, None, "pytest passed and all golden I/O matched")


def verify(candidate_path, test_suite_path, golden_path, timeout=10.0):
    """Boolean contract kept for build_case.py: (ok, reason)."""
    r = classify(candidate_path, test_suite_path, golden_path, timeout)
    return r.ok, r.reason


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: python verify_case.py <candidate.py> <test_suite.py> "
                 "<golden_io.json>")
    ok, reason = verify(*sys.argv[1:4])
    print("PASS" if ok else "FAIL: " + reason)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
