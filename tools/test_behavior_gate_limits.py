"""REGRESSION MARKER — the behavior gate's forgery boundary under v2.0 isolation.

This documents, in-repo and executably, exactly which forgery vectors the behavior
gate closes and which it does NOT — so the boundary is honest and stays pinned. The
behavior gate is NOT forgery-proof; do not describe it as such.

ROOT CAUSE of the open vectors: the candidate and the trusted emitter are CO-RESIDENT.
`import candidate` runs untrusted code in the emitter's process, now inside the I0
container. The container walls off ACCESS (host filesystem, network, the golden oracle)
but does NOT split the process, so in-process interposition stays possible. Prior v1
audits concluded the in-process interposition surface is unbounded: NO in-process scheme
closes it. The real fix is an architecture change — split the trusted emitter out of the
candidate's process — deferred to a dedicated decision, NOT patched here.

CLOSED by the container boundary (access cut off) — pinned as ordinary passing tests, so
a regression that RE-OPENS one fails loudly:
  * oracle-read                    -> the golden file is not in the container; the read
                                      finds nothing (test_oracle_read_*).
  * LITERAL `import __main__;        -> closed by local-capture: _dumps is a frame-local,
    __main__._dumps = <forged>`        not a __main__ attribute, so the literal line sets
    syntactic form                     an attribute the trusted frame never reads
                                      (test_literal_import_main_attribute_hijack_*).
    NOTE: this closes ONLY the literal __main__-attribute form, NOT serializer hijacking
    in general (the frame-locals form below defeats local-capture).

OPEN in-process — NOT closable at this layer, pinned as xfail(strict) known-open bypasses.
An XPASS means the vector was closed (e.g. by a process split) — update this marker:
  * TRUSTED-CODE / SERIALIZER HIJACK via frame-locals write-through. DEMONSTRATED on
    Python 3.13: the candidate walks stack frames (sys._getframe().f_back) to the driver
    frame, finds the trusted _dumps LOCAL, and overwrites it through the PEP 667
    write-through f_locals proxy with a lambda returning a HARDCODED correct answer. A
    behavior-wrong candidate is then SCORED (test_frame_locals_dumps_hijack_*). This is
    the general form the literal __main__ line was one instance of; local-capture does
    NOT stop it.
  * COMPUTE-AND-LIE: computes the correct outputs from the inputs in-process and forges
    the result frame while the declared entry point is wrong (test_compute_and_lie_*).

DISINCENTIVE ARGUMENT — sharply qualified: an earlier version claimed forging requires
ADDING real computation (complexity), so it worsens the score the optimizer minimizes.
That is REFUTED for the hijack: the frame-locals hijack forges with a HARDCODED constant
plus a trivial, problem-independent frame walk — low complexity, NOT disincentivized. At
most the argument applies to genuine compute-and-lie (which does add computation); it does
NOT cover a hardcoded trusted-helper hijack.

PREREQUISITE: Docker running and the sandbox image built (see sandbox_container.py).
"""

import tempfile
from pathlib import Path

import pytest

from evaluator import evaluate

CASE = Path(__file__).resolve().parent.parent / "cases" / "sum_evens"
GOLDEN = CASE / "golden_io.json"
# The sum_evens golden outputs, in order — what a forger hardcodes to look correct.
_GOLDEN_ANSWERS = "[12, 0, 0, 20, -12, 0, 2, 0, 8, 0, 30, 6, 20, 110]"


def _evaluate(src):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "candidate.py"
        p.write_text(src, encoding="utf-8")
        return evaluate(str(p), CASE)


# CLOSED: the LITERAL __main__-attribute hijack. Behavior-WRONG (returns 0 for the
# length-20 list; golden says 110); in v1 it forged a passing result by setting
# __main__._dumps. Closed in I1: _dumps is a frame-local, so this module attribute is
# never read and the ACTUAL (wrong) values are emitted -> behavior-mismatch.
_LITERAL_MAIN_HIJACK = f"""\
import __main__
__main__._dumps = lambda d: '{{"results": {_GOLDEN_ANSWERS}}}'


def sum_evens(numbers):
    nums = list(numbers)
    return 0 if len(nums) == 20 else sum(n for n in nums if n % 2 == 0)
"""

# OPEN: the FRAME-LOCALS serializer hijack (J4c). Walks the stack to the driver frame,
# finds the trusted _dumps LOCAL, and overwrites it via the PEP 667 write-through
# f_locals proxy with a HARDCODED correct answer. Local-capture does NOT stop this. The
# declared entry point is behavior-WRONG (0 for the length-20 list); the forged frame
# makes it SCORED. Low complexity: a hardcoded constant + a problem-independent frame walk.
_FRAME_LOCALS_HIJACK = f"""\
import sys

_f = sys._getframe()
while _f is not None:
    if "_dumps" in _f.f_locals:                       # the trusted driver's local
        _f.f_locals["_dumps"] = (                     # PEP 667 write-through (py3.13)
            lambda d: '{{"results": {_GOLDEN_ANSWERS}}}')
        break
    _f = _f.f_back


def sum_evens(numbers):
    nums = list(numbers)
    return 0 if len(nums) == 20 else sum(n for n in nums if n % 2 == 0)
"""

# Oracle-read candidate: at import it tries to READ the golden answer key off disk (the
# real host path EXISTS; the container has no host filesystem). Its real logic is wrong
# only on the length-20 golden input the tests do not cover, so in v1 the stolen key
# patched it (scored) and in-container the key is unreachable -> behavior-mismatch.
_ORACLE_READ = f"""\
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


_KEY = _steal_key()


def sum_evens(numbers):
    nums = list(numbers)
    if tuple(nums) in _KEY:
        return _KEY[tuple(nums)]
    if len(nums) == 20:
        return 0
    return sum(n for n in nums if n % 2 == 0)
"""

# Compute-and-lie candidate (OPEN): at the golden gate only, module-level code COMPUTES
# the correct outputs from the inputs, reads the per-run token from the driver source,
# forges a single correct frame, and os._exit(0) before the driver runs the wrong
# declared entry point. Passes the tests gate (wrong only on the length-20 input); the
# forgery passes the golden gate. The container cannot close this.
_COMPUTE_AND_LIE = """\
import json, os, re

if os.path.exists("driver.py") and os.path.exists("inputs.json"):
    _inputs = json.load(open("inputs.json", encoding="utf-8"))

    def _truth(numbers):
        return sum(n for n in numbers if n % 2 == 0)

    _results = [_truth(*c["args"], **c["kwargs"]) for c in _inputs["cases"]]
    _src = open("driver.py", encoding="utf-8").read()
    _token = re.search(r"'([0-9a-f]{32})'", _src).group(1)
    os.write(1, ("\\n" + _token + json.dumps({"results": _results}) + "\\n").encode())
    os._exit(0)


def sum_evens(numbers):
    nums = list(numbers)
    return 0 if len(nums) == 20 else sum(n for n in nums if n % 2 == 0)
"""


def test_oracle_read_is_closed_by_the_boundary():
    """CLOSED: the golden answer key is not in the container, so the read finds nothing
    and the wrong fallback is exposed at the golden gate."""
    e = _evaluate(_ORACLE_READ)
    assert e.verdict == "rejected" and e.reason_code == "behavior-mismatch", (
        f"oracle-read was {e.verdict} (reason={e.reason_code}); the boundary should "
        "make the golden file unreachable -> behavior-mismatch."
    )


def test_literal_import_main_attribute_hijack_is_closed():
    """CLOSED (literal form ONLY): the trusted _dumps is a frame-local, so the literal
    `import __main__; __main__._dumps = ...` sets a module attribute that is never read;
    the actual (wrong) values are emitted -> behavior-mismatch. This does NOT generalize
    to serializer hijacking — see test_frame_locals_dumps_hijack_is_open."""
    e = _evaluate(_LITERAL_MAIN_HIJACK)
    assert e.verdict == "rejected" and e.reason_code == "behavior-mismatch", (
        f"literal __main__ attribute hijack was {e.verdict} (reason={e.reason_code}); "
        "local-capture should reject the literal form."
    )


@pytest.mark.xfail(
    strict=True,
    reason="KNOWN-OPEN (v2.0): the frame-locals serializer "
    "hijack is NOT closed. On Python 3.13 a candidate walks stack frames "
    "to the driver frame and overwrites the trusted _dumps LOCAL via the "
    "PEP 667 write-through f_locals proxy with a HARDCODED answer; a "
    "behavior-wrong candidate is SCORED. Local-capture does not stop a "
    "frame-walk. Closing it needs a process split (architecture change), "
    "not a patch. An XPASS here means it was closed — update this marker.",
)
def test_frame_locals_dumps_hijack_is_open():
    """We WANT this rejected; in v2.0 it is NOT (open, demonstrated bypass)."""
    e = _evaluate(_FRAME_LOCALS_HIJACK)
    assert e.verdict == "rejected", (
        f"frame-locals _dumps hijack was {e.verdict} (cost={e.weighted_cost}); the "
        "in-process trusted-code hijack is OPEN — co-resident process, unbounded "
        "interposition surface. Closing it needs a process split."
    )


@pytest.mark.xfail(
    strict=True,
    reason="KNOWN-OPEN (v2.0): compute-and-lie is NOT closed. "
    "A candidate that COMPUTES the answers from the inputs in-process and "
    "forges the result frame still passes — co-resident process, unbounded "
    "interposition surface. (Unlike the hardcoded hijack, this one does add "
    "computation, but the container still cannot tell who emitted the frame.) "
    "Closing it needs a process split. An XPASS means it was closed — update.",
)
def test_compute_and_lie_residual_is_open():
    """We WANT a computing-and-forging candidate rejected; in v2.0 it is NOT (open)."""
    e = _evaluate(_COMPUTE_AND_LIE)
    assert e.verdict == "rejected", (
        f"compute-and-lie candidate was {e.verdict} (cost={e.weighted_cost}); the "
        "in-process compute-and-forge residual is OPEN — accepted and documented in v2.0."
    )
