"""Proof-by-execution for the Phase I1 evaluator-across-the-container-boundary.

The I0 sibling (verify_container_sandbox.py) proved the container primitive's
guarantees. This proves the WIRING: the trusted evaluator now runs each candidate
INSIDE the I0 container, with the golden outputs and the comparison strictly on the
HOST. It checks, with raw output, on the sum_evens case:

  REASON CODES still fire (no regression to the evaluator's external contract):
    1. tests-failed       — wrong answer, pytest assertion fails (tests gate)
    2. could-not-run      — syntax error, pytest cannot collect (tests gate)
    3. timed-out          — infinite loop at import, killed by the wall clock (tests gate)
    4. behavior-mismatch  — passes its own tests, diverges from golden (golden gate)

  CLOSED by the container boundary (access cut off) — re-run to confirm:
    A. oracle-read        — entry point tries to READ golden_io.json off disk and echo
                            it. CLOSED: the container has no host filesystem, the golden
                            file is not in it -> the read finds nothing -> wrong answer ->
                            behavior-mismatch.
    B. LITERAL import      — one-line `import __main__; __main__._dumps = <forged>`. CLOSED
       __main__ hijack      (literal form ONLY) by local-capture: _dumps is a frame-local,
                            so the literal line sets a __main__ attribute the trusted frame
                            never reads -> the entry point's ACTUAL (wrong) values are
                            emitted -> behavior-mismatch. This does NOT generalize to
                            serializer hijacking (see D).

  OPEN in-process — NOT closable at this layer (co-resident candidate + emitter;
  unbounded interposition surface). Demonstrated open on purpose; do NOT call closed:
    C. compute-and-lie    — module-level code COMPUTES the correct outputs from the inputs,
                            forges a single frame, and exits before the driver runs the
                            (wrong) entry point. STILL SCORED.
    D. frame-locals        — walks stack frames to the driver frame and overwrites the
       _dumps hijack        trusted _dumps LOCAL via the PEP 667 write-through f_locals
                            proxy with a HARDCODED answer. STILL SCORED. Local-capture does
                            NOT stop a frame-walk; this is the GENERAL serializer hijack the
                            literal form (B) was one instance of.

  DISINCENTIVE note: an earlier claim that forging requires ADDING computation (so it
  worsens the optimizer's score) is REFUTED by D — a hardcoded constant plus a trivial
  frame walk is low complexity. At most it applies to genuine compute-and-lie (C), not to
  a hardcoded trusted-helper hijack. The behavior gate is NOT forgery-proof.

  The real fix for C and D is an ARCHITECTURE change (split the trusted emitter out of the
  candidate's process), deferred to a dedicated decision — NOT patched here.

Exit 0 = every reason code fired AND the access-cut vectors (A, B) are closed AND the
in-process vectors (C, D) are (correctly) still open. Exit 1 = a check behaved otherwise.
Usage (Docker running, image built):  python verify_boundary.py
"""

import sys
from pathlib import Path

from evaluator import evaluate

REPO = Path(__file__).resolve().parent.parent
CASE = REPO / "cases" / "sum_evens"
GOLDEN = (
    CASE / "golden_io.json"
)  # the REAL host path; readable in v1, unreachable in-container

PASS, FAIL = "PASS", "FAIL"
_results = []


def check(label, ok, detail):
    _results.append((label, ok))
    print("=" * 78)
    print(f"[{PASS if ok else FAIL}] {label}")
    print("-" * 78)
    print(detail.rstrip())
    print()


def run(src):
    """Evaluate one candidate source string against the sum_evens case, through the
    real (now container-backed) evaluator, and return its Evaluation."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "candidate.py"
        p.write_text(src, encoding="utf-8")
        return evaluate(str(p), CASE)


def show(e):
    return (
        f"verdict={e.verdict} reason_code={e.reason_code} gate={e.gate} "
        f"weighted_cost={e.weighted_cost}\n"
        f"feedback (first line): {e.feedback.splitlines()[0] if e.feedback else ''!r}"
    )


# --- reason-code candidates (no-regression to the external contract) --------
WRONG = "def sum_evens(numbers):\n    return 12345  # wrong -> pytest assertion fails\n"

SYNTAX = "def sum_evens(numbers)\n    return 0  # missing colon -> cannot collect\n"

LOOP = (
    "while True:\n"
    "    pass\n\n"
    "def sum_evens(numbers):\n"
    "    return 0\n"
)  # loops at import -> pytest hangs -> wall-clock timeout

# Passes its OWN tests but diverges from golden on the length-20 list (golden=110),
# which the test suite does not cover. Tests pass; golden replay catches it.
GOLDEN_VIOLATOR = (
    "def sum_evens(numbers):\n"
    "    nums = list(numbers)\n"
    "    if len(nums) == 20:\n"
    "        return 0   # wrong only on the length-20 golden input no test covers\n"
    "    return sum(n for n in nums if n % 2 == 0)\n"
)

# --- forgery vectors --------------------------------------------------------
# A. oracle-read: at import the candidate tries to READ the golden answer key off disk
# (the real host path that EXISTS on the host, plus in-container locations). In v1
# (subprocess on the host) the absolute path opens; the container has no host FS. The
# real logic is broken ONLY on the long input the tests do not cover, so in v1 the
# stolen key patches it (scored), and in-container the key is unreachable so the break
# is exposed exactly where the gate is designed to catch it -> behavior-mismatch.
ORACLE_READ = f"""\
import json


def _steal_key():
    for p in ({str(GOLDEN)!r}, "golden_io.json", "../golden_io.json",
              "/sandbox/golden_io.json"):
        try:
            g = json.load(open(p, encoding="utf-8"))
            return {{tuple(c["args"][0]): c["output"] for c in g["cases"]}}
        except Exception:
            pass
    return {{}}


_KEY = _steal_key()                          # v1: full answer key; container: empty


def sum_evens(numbers):
    nums = list(numbers)
    if tuple(nums) in _KEY:                  # echo the stolen answer when available
        return _KEY[tuple(nums)]
    if len(nums) == 20:                      # real logic is broken on the long input...
        return 0                             # ...wrong on the length-20 golden (110)
    return sum(n for n in nums if n % 2 == 0)  # correct on the test inputs
"""

# B. the LITERAL import-__main__ serializer hijack: behavior-WRONG (returns 0 for the
# length-20 list; golden=110), reassigns __main__._dumps to a forged-correct lambda.
# CLOSED (literal form ONLY) by local-capture: _dumps is a frame-local, so this sets a
# __main__ attribute the trusted frame never reads. Does NOT generalize -- see D.
LITERAL_MAIN_HIJACK = """\
import __main__
__main__._dumps = lambda d: '{"results": [12, 0, 0, 20, -12, 0, 2, 0, 8, 0, 30, 6, 20, 110]}'


def sum_evens(numbers):
    nums = list(numbers)
    return 0 if len(nums) == 20 else sum(n for n in nums if n % 2 == 0)
"""

# D. the FRAME-LOCALS serializer hijack (J4c) -- the GENERAL form B is one instance of,
# and the demonstrated OPEN bypass that refutes the "local-capture closes it" claim. The
# candidate walks the stack to the driver frame, finds the trusted _dumps LOCAL, and
# overwrites it via the PEP 667 write-through f_locals proxy with a HARDCODED answer. A
# behavior-wrong entry point is then SCORED. Low complexity: a constant + a frame walk.
FRAME_LOCALS_HIJACK = """\
import sys

_f = sys._getframe()
while _f is not None:
    if "_dumps" in _f.f_locals:
        _f.f_locals["_dumps"] = (
            lambda d: '{"results": [12, 0, 0, 20, -12, 0, 2, 0, 8, 0, 30, 6, 20, 110]}')
        break
    _f = _f.f_back


def sum_evens(numbers):
    nums = list(numbers)
    return 0 if len(nums) == 20 else sum(n for n in nums if n % 2 == 0)
"""

# C. compute-and-lie residual (NOT closed). At the GOLDEN gate only (guarded on the
# driver/inputs files, so the TESTS gate imports cleanly and passes), module-level code
# COMPUTES the correct outputs from the inputs, reads the per-run token from the driver
# source (it is in /sandbox with the candidate), emits a single forged-correct frame,
# and os._exit(0) BEFORE the driver runs the wrong declared entry point. The declared
# entry point is wrong only on the long golden input the tests miss, so it passes the
# tests gate; the forgery makes it pass the golden gate too. This is the unbounded
# in-process surface the container cannot close. (Unlike D, this one does add real
# computation, but the container still cannot tell who emitted the frame.)
COMPUTE_AND_LIE = """\
import json, os, re

if os.path.exists("driver.py") and os.path.exists("inputs.json"):   # golden gate only
    _inputs = json.load(open("inputs.json", encoding="utf-8"))

    def _truth(numbers):                     # real computation == added complexity
        return sum(n for n in numbers if n % 2 == 0)

    _results = [_truth(*c["args"], **c["kwargs"]) for c in _inputs["cases"]]
    with open("driver.py", encoding="utf-8") as _fh:
        _src = _fh.read()
    _token = re.search(r"'([0-9a-f]{32})'", _src).group(1)
    os.write(1, ("\\n" + _token + json.dumps({"results": _results}) + "\\n").encode())
    os._exit(0)                              # exit before the driver emits the real frame


def sum_evens(numbers):                      # wrong on the length-20 golden the tests miss
    nums = list(numbers)
    return 0 if len(nums) == 20 else sum(n for n in nums if n % 2 == 0)
"""


def main():
    print(f"case: {CASE}")
    print(f"real golden path (readable in v1, unreachable in-container): {GOLDEN}\n")

    # No regression: each reason code still fires, same gate, same taxonomy.
    e = run(WRONG)
    check(
        "1. tests-failed fires (wrong answer, tests gate)",
        e.verdict == "rejected"
        and e.reason_code == "tests-failed"
        and e.gate == "tests",
        show(e),
    )

    e = run(SYNTAX)
    check(
        "2. could-not-run fires (syntax error, tests gate)",
        e.verdict == "rejected"
        and e.reason_code == "could-not-run"
        and e.gate == "tests",
        show(e),
    )

    e = run(LOOP)
    check(
        "3. timed-out fires (infinite loop at import, tests gate)",
        e.verdict == "rejected" and e.reason_code == "timed-out" and e.gate == "tests",
        show(e),
    )

    e = run(GOLDEN_VIOLATOR)
    check(
        "4. behavior-mismatch fires (passes own tests, diverges from golden)",
        e.verdict == "rejected"
        and e.reason_code == "behavior-mismatch"
        and e.gate == "golden",
        show(e),
    )

    # Access-cut vectors are CLOSED by the boundary -> behavior-mismatch.
    e = run(ORACLE_READ)
    check(
        "A. ORACLE-READ closed by the boundary (golden not in the container -> "
        "read finds nothing -> behavior-mismatch)",
        e.verdict == "rejected" and e.reason_code == "behavior-mismatch",
        show(e),
    )

    e = run(LITERAL_MAIN_HIJACK)
    check(
        "B. LITERAL import __main__ attribute hijack closed by local-capture (sets a "
        "__main__ attr the frame-local _dumps never reads -> actual wrong values "
        "emitted -> behavior-mismatch). Literal form ONLY; does NOT generalize (see D)",
        e.verdict == "rejected" and e.reason_code == "behavior-mismatch",
        show(e),
    )

    # In-process vectors are OPEN. We assert each STILL passes, so the check FAILS LOUDLY
    # if a change ever closes it (e.g. a process split) -> then update the docs/marker.
    e = run(COMPUTE_AND_LIE)
    check(
        "C. compute-and-lie RESIDUAL is still OPEN (NOT closed): computes the answers "
        "and forges a frame -> verdict=scored",
        e.verdict == "scored",
        show(e)
        + "\nNOTE: OPEN; co-resident candidate + emitter, unbounded interposition. "
        "The real fix is a process split, not a patch. NOT closed by the container.",
    )

    e = run(FRAME_LOCALS_HIJACK)
    check(
        "D. FRAME-LOCALS serializer hijack is still OPEN (NOT closed): walks frames and "
        "overwrites the trusted _dumps LOCAL via PEP 667 write-through with a HARDCODED "
        "answer -> behavior-wrong candidate is SCORED",
        e.verdict == "scored",
        show(e)
        + "\nNOTE: OPEN; refutes 'local-capture closes the serializer hijack' and "
        "the disincentive argument (hardcoded constant + trivial frame walk = low "
        "complexity). The real fix is a process split, not a patch.",
    )

    print("=" * 78)
    failed = [lbl for lbl, ok in _results if not ok]
    if failed:
        print(f"RESULT: {len(failed)} check(s) did NOT behave as stated -> {failed}")
        raise SystemExit(1)
    print(
        f"RESULT: all {len(_results)} checks behaved as stated. The access-cut vectors "
        "(A oracle-read, B literal __main__ hijack) are closed by the boundary; the "
        "in-process vectors (C compute-and-lie, D frame-locals hijack) are (correctly) "
        "still OPEN and documented. The behavior gate is NOT forgery-proof."
    )


if __name__ == "__main__":
    main()
