"""The standing oracle-leak guarantee (N2, decision 0025).

The candidate generator must NEVER see the oracle (Fork 3, decision 0012). The
multi-file equivalence rejection embeds the oracle in its witness outcome lines,
and a tests-failed rejection can embed it in a pytest dump. mloop.format_feedback
strips both before any feedback reaches the generator.

These tests are the standing guard. Each builds a rejection through the REAL
mevaluator producer (with a distinctive sentinel where the oracle would be) in a
real MEvaluation carrying the gate and reason_code mevaluator actually sets, then
runs it through the REAL mloop.format_feedback and asserts the sentinel never
survives. Because the whole path is real -- producer format, routing, and strip --
the test fails on a leak from ANY cause: a producer prefix change, a routing-key
drift that misroutes the rejection, or a witness-format change. It never asserts
against a string the test itself wrote in the oracle line format; the sentinels are
plain outcome values, and a precondition check proves the raw producer feedback
actually carried the oracle before the strip ran.

  cd tools && python -m pytest test_oracle_leak.py -q -p no:cacheprovider
"""

import mevaluator
import mloop
from oracle_markers import CANDIDATE_OUTCOME_PREFIX, ORIGINAL_OUTCOME_PREFIX
from verify_case import TESTS_FAILED

# Distinctive sentinels standing in for the oracle's outcome values -- plain values,
# NOT oracle-format lines: the test asserts these never reach the generator.
ORIG_OUTCOME_SENTINEL = "ORACLE_ORIGINAL_OUTCOME_4f91ac"
CAND_OUTCOME_SENTINEL = "CANDIDATE_OUTCOME_b73e20"
# A marker for the diverging INPUT, which Fork 1 PERMITS forwarding.
DIVERGING_INPUT_SENTINEL = "seq_INPUT_KEPT_d2c8"
DUMP_ORACLE_SENTINEL = "EXPECTED_ORACLE_FROM_DUMP_a17b"


def test_equivalence_rejection_strips_oracle_keeps_input():
    """Equivalence vector: real producer + real routing. Both outcome sentinels are
    stripped (Fork 3); the diverging-input sentinel survives (Fork 1)."""
    witness = {
        "sequence": DIVERGING_INPUT_SENTINEL,
        "call_index": 4,
        "call": "withdraw(250)",
        "original": ORIG_OUTCOME_SENTINEL,
        "candidate": CAND_OUTCOME_SENTINEL,
    }
    # Built exactly as mevaluator.evaluate builds an equivalence rejection: real
    # producer, the gate and reason_code mevaluator itself sets.
    ev = mevaluator.MEvaluation(
        "rejected",
        mevaluator.NON_EQUIVALENT,
        "equivalence",
        None,
        None,
        None,
        feedback=mevaluator._reject_equivalence_feedback(witness, {"sequences": 5}),
    )

    # Precondition: the RAW producer feedback really carries the oracle, so the strip
    # below has something to strip (the assertions are not a vacuous pass).
    assert ORIG_OUTCOME_SENTINEL in ev.feedback
    assert CAND_OUTCOME_SENTINEL in ev.feedback

    out = mloop.format_feedback(ev)
    assert ORIG_OUTCOME_SENTINEL not in out  # the oracle's outcome never leaks
    assert CAND_OUTCOME_SENTINEL not in out  # the candidate's outcome is dropped too
    assert (
        DIVERGING_INPUT_SENTINEL in out
    )  # the diverging INPUT is still named (Fork 1)
    assert "withdraw(250)" in out  # the diverging call (input) is kept


def test_tests_failed_rejection_strips_dump_oracle():
    """Tests-failed vector: real producer + real routing. The pytest dump (which can
    print the oracle's expected value) is replaced by the generic message."""
    dump = (
        "pytest: tests-failed:\n"
        "E       assert limiter.allow('x') == " + DUMP_ORACLE_SENTINEL
    )
    ev = mevaluator.MEvaluation(
        "rejected",
        TESTS_FAILED,
        "tests",
        None,
        None,
        None,
        feedback=mevaluator._reject_tests_feedback(TESTS_FAILED, dump),
    )

    assert DUMP_ORACLE_SENTINEL in ev.feedback  # precondition: the raw dump carries it
    out = mloop.format_feedback(ev)
    assert DUMP_ORACLE_SENTINEL not in out  # the dump (and its oracle) never leaks
    assert "Re-examine" in out  # the generic behavior-changed message


def test_producer_and_sanitizer_bind_to_one_marker():
    """The producer emits the oracle lines with the shared prefixes, and those are
    exactly the prefixes the sanitizer strips -- one source, no per-file copy."""
    witness = {
        "sequence": "s",
        "call_index": 0,
        "call": "c",
        "original": ORIG_OUTCOME_SENTINEL,
        "candidate": CAND_OUTCOME_SENTINEL,
    }
    fb = mevaluator._reject_equivalence_feedback(witness, {})
    orig_line = next(
        ln.strip() for ln in fb.splitlines() if ORIG_OUTCOME_SENTINEL in ln
    )
    cand_line = next(
        ln.strip() for ln in fb.splitlines() if CAND_OUTCOME_SENTINEL in ln
    )
    assert orig_line.startswith(ORIGINAL_OUTCOME_PREFIX)
    assert cand_line.startswith(CANDIDATE_OUTCOME_PREFIX)
