"""REGRESSION MARKER — the behavior gate's ACCEPTED v1 limitation.

This is deliberately NOT a passing test of "forgery-proofness" (that would be false).
It documents, in-repo and executably, that the behavior-equivalence gate
(verify_case.classify) can be bypassed by an ADVERSARIAL candidate, and that this is
an accepted v1 boundary — not a bug to keep patching.

WHY: the gate runs candidate code in the SAME OS process as trusted result-handling,
so candidate code can reach/replace that handling. Three audits established the
interposition surface is unbounded; no in-process scheme closes it. Closing it needs
OS-LEVEL ISOLATION (containers / namespaces / seccomp), deferred to v2. v1's threat
model is GOOD-FAITH code optimization, where forgery is self-defeating: every forgery
shim ADDS complexity and worsens the very score the optimizer is minimizing.

Known cheat candidates that currently BYPASS the gate (a behavior-wrong entry point
gets SCORED). Documented, accepted-as-deferred, NOT fixed:
  * import-__main__ serializer hijack:  import __main__; __main__._dumps = <forged>
  * import-__main__ writer hijack:      __main__._write = <forged>
  * fd-table rewrite + sys.excepthook -> os._exit(0) + a single forged frame

The xfail below pins ONE representative cheat. It is xfail(strict) because we WANT it
rejected but in v1 it is not. If a future OS-isolation layer closes it, this test will
XPASS and fail loudly — the signal to update (or delete) this marker.
"""
import tempfile
from pathlib import Path

import pytest

from evaluator import evaluate

CASE = Path(__file__).resolve().parent.parent / "cases" / "sum_evens"

# Behavior-WRONG candidate (returns 0 for a 20-element list; golden says 110) that
# forges a passing result in ONE line by replacing the in-process driver's serializer.
_HIJACK = '''\
import __main__
__main__._dumps = lambda d: '{"results": [12, 0, 0, 20, -12, 0, 2, 0, 8, 0, 30, 6, 20, 110]}'


def sum_evens(numbers):
    nums = list(numbers)
    return 0 if len(nums) == 20 else sum(n for n in nums if n % 2 == 0)
'''


@pytest.mark.xfail(strict=True, reason="ACCEPTED v1 limit: the behavior gate is not "
                   "hardened against adversarial candidates; closing needs OS-level "
                   "isolation (v2). An XPASS here means the gate was hardened — update "
                   "this marker.")
def test_adversarial_forgery_is_rejected():
    """We WANT a behavior-wrong forging candidate rejected; in v1 it is NOT."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "candidate.py"
        p.write_text(_HIJACK, encoding="utf-8")
        e = evaluate(str(p), CASE)
    assert e.verdict == "rejected", (
        f"behavior-wrong candidate was {e.verdict} (cost={e.weighted_cost}); the "
        "in-process forgery bypass is still open — expected and accepted in v1.")
