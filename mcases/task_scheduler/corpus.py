"""Sequence corpus for task_scheduler. The load-bearing artifact.

Gap-class coverage (per the M0 findings):
1. Unreached input subdomains -> PER-METHOD VALIDATION PROBES: every public
   method that takes arguments gets invalid, boundary-invalid, and
   boundary-valid arguments (submit id/priority/retries; complete, fail,
   cancel, status ids), plus wrong-state and unknown-id probes. Argless
   methods (next_job, pending, stats) are probed in empty/odd states.
2. Unreached deep states -> DEEP-STATE REACHERS: retry chains to
   exhaustion at every retries value 0..5, resubmission after every
   terminal state, a 30-job multi-priority drain, cancel-heavy states.
3. Order dependence -> explicit FIFO tie-break discriminators, requeue-
   to-back discriminators, permuted submit orders, interleaved
   fail/submit orderings.
Plus 300 seeded random walks over a collision-heavy domain for breadth.
Every sequence ends with stats() + pending() as a full observable digest.
"""
import random

DIGEST = [("stats", ()), ("pending", ())]


def _seq(name, calls):
    return (name, (), calls + DIGEST)


def _validation_probes():
    out = []
    bad_ids = [("", ), ("x" * 65,), (7,), (None,), (True,)]
    # submit: every argument, invalid + boundary-valid
    out.append(_seq("probe_submit_id", [
        ("submit", bad) for bad in bad_ids
    ] + [("submit", ("x" * 64,)), ("status", ("x" * 64,))]))
    out.append(_seq("probe_submit_priority", [
        ("submit", ("a",), {"priority": bad})
        for bad in (-11, 11, True, False, "5", 1.5, None)
    ] + [("submit", ("lo",), {"priority": -10}),
         ("submit", ("hi",), {"priority": 10})]))
    out.append(_seq("probe_submit_retries", [
        ("submit", ("a",), {"retries": bad})
        for bad in (-1, 6, True, "2", None, 2.0)
    ] + [("submit", ("r0",), {"retries": 0}),
         ("submit", ("r5",), {"retries": 5})]))
    # every id-taking method: invalid format, unknown id, wrong state
    for method in ("complete", "fail", "cancel", "status"):
        out.append(_seq(f"probe_{method}_id", [
            (method, bad) for bad in bad_ids
        ] + [(method, ("ghost",))]))
    out.append(_seq("probe_wrong_state", [
        ("submit", ("q",)),
        ("complete", ("q",)), ("fail", ("q",)),          # queued, not running
        ("submit", ("d",), {"retries": 0}),
        ("next_job", ()), ("next_job", ()),
        ("complete", ("q",)),                            # still queued? no: q running now
        ("fail", ("d",)),
        ("cancel", ("d",)),                              # dead -> job not active
        ("complete", ("d",)),
    ]))
    # argless methods in empty state
    out.append(_seq("probe_empty_state", [
        ("next_job", ()), ("pending", ()), ("stats", ()), ("next_job", ()),
    ]))
    return out


def _deep_state_reachers():
    out = []
    for r in range(6):  # retry exhaustion at every allowed retries value
        calls = [("submit", ("job",), {"retries": r})]
        for _ in range(r + 1):
            calls += [("next_job", ()), ("fail", ("job",)), ("status", ("job",))]
        calls += [("next_job", ()), ("fail", ("job",))]   # extra: must error
        out.append(_seq(f"deep_retry_exhaustion_{r}", calls))
    out.append(_seq("deep_resubmit_after_each_terminal", [
        ("submit", ("a",), {"retries": 0}),
        ("next_job", ()), ("complete", ("a",)), ("submit", ("a",)),   # after done
        ("cancel", ("a",)), ("submit", ("a",)),                       # after cancelled
        ("next_job", ()), ("fail", ("a",)),
        ("submit", ("a",), {"retries": 0}),                           # after dead
        ("status", ("a",)),
    ]))
    big_drain = []
    for i in range(30):
        big_drain.append(("submit", (f"j{i}",), {"priority": (i % 5) - 2}))
    big_drain += [("next_job", ()) for _ in range(31)]
    out.append(_seq("deep_30_job_drain", big_drain))
    out.append(_seq("deep_cancel_heavy", [
        ("submit", (f"c{i}",), {"priority": i % 3}) for i in range(10)
    ] + [("cancel", (f"c{i}",)) for i in range(0, 10, 2)
    ] + [("next_job", ()) for _ in range(6)
    ] + [("cancel", ("c1",)),                       # running by now? exercise it
         ("status", ("c0",)), ("status", ("c1",))]))
    return out


def _order_dependence():
    out = []
    out.append(_seq("order_fifo_tie_break", [
        ("submit", ("first",), {"priority": 3}),
        ("submit", ("second",), {"priority": 3}),
        ("submit", ("third",), {"priority": 3}),
        ("pending", ()),
        ("next_job", ()), ("next_job", ()), ("next_job", ()),
    ]))
    out.append(_seq("order_requeue_to_back", [
        ("submit", ("a",), {"retries": 2}),
        ("submit", ("b",)),
        ("next_job", ()),                  # a runs
        ("fail", ("a",)),                  # a requeues BEHIND b
        ("pending", ()),
        ("next_job", ()),                  # must be b
        ("next_job", ()),                  # then a again
    ]))
    out.append(_seq("order_submit_permutation_1", [
        ("submit", ("x",), {"priority": 1}), ("submit", ("y",), {"priority": 2}),
        ("submit", ("z",), {"priority": 1}),
        ("pending", ()), ("next_job", ()), ("pending", ()),
    ]))
    out.append(_seq("order_submit_permutation_2", [
        ("submit", ("z",), {"priority": 1}), ("submit", ("y",), {"priority": 2}),
        ("submit", ("x",), {"priority": 1}),
        ("pending", ()), ("next_job", ()), ("pending", ()),
    ]))
    out.append(_seq("order_interleaved_fail_submit", [
        ("submit", ("a",), {"priority": 1, "retries": 3}),
        ("next_job", ()),
        ("submit", ("b",), {"priority": 1}),
        ("fail", ("a",)),                  # a goes behind b
        ("submit", ("c",), {"priority": 1}),
        ("pending", ()),                   # b, a, c
        ("next_job", ()), ("next_job", ()), ("next_job", ()),
    ]))
    out.append(_seq("order_cancel_then_drain", [
        ("submit", ("a",), {"priority": 2}), ("submit", ("b",), {"priority": 2}),
        ("submit", ("c",), {"priority": 2}),
        ("cancel", ("b",)),
        ("pending", ()), ("next_job", ()), ("next_job", ()), ("next_job", ()),
    ]))
    return out


def _generated(n_sequences=300, seed=20260612):
    ids = ["a", "b", "c", "d", "e", "f"]
    out = []
    for i in range(n_sequences):
        rng = random.Random(seed + i)
        length = rng.randint(10, 80)
        calls = []
        for _ in range(length):
            r = rng.random()
            jid = rng.choice(ids)
            if r < 0.30:
                kwargs = {}
                if rng.random() < 0.6:
                    kwargs["priority"] = rng.randint(-2, 2)
                if rng.random() < 0.5:
                    kwargs["retries"] = rng.randint(0, 2)
                calls.append(("submit", (jid,), kwargs))
            elif r < 0.50:
                calls.append(("next_job", ()))
            elif r < 0.62:
                calls.append(("complete", (jid,)))
            elif r < 0.76:
                calls.append(("fail", (jid,)))
            elif r < 0.84:
                calls.append(("cancel", (jid,)))
            elif r < 0.92:
                calls.append(("status", (jid,)))
            elif r < 0.96:
                calls.append(("pending", ()))
            else:
                calls.append(("stats", ()))
            if rng.random() < 0.04:
                calls.append(rng.choice([
                    ("submit", ("",)),
                    ("submit", ("y" * 65,)),
                    ("submit", (jid,), {"priority": 99}),
                    ("submit", (jid,), {"retries": -1}),
                    ("status", (3,)),
                    ("cancel", ("",)),
                ]))
        out.append(_seq(f"rand-{i}", calls))
    return out


def build_corpus():
    return (_validation_probes() + _deep_state_reachers()
            + _order_dependence() + _generated())
