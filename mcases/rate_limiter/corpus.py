"""Sequence corpus for rate_limiter.

Gap-class coverage (per the M0 findings):
1. Unreached input subdomains -> PER-METHOD VALIDATION PROBES: constructor
   rate and burst (each separately, invalid + boundary-valid), client-key
   probes on allow/remaining/reset, tick(n) probes, unknown-client probes.
2. Unreached deep states -> DEEP-STATE REACHERS: drain to exactly zero and
   one past it, refill at the exact boundary tick, clamp after long idle,
   repeated drain/refill cycles, reset in drained and full states.
3. Order dependence -> allow/tick interleavings that must differ, the same
   ops permuted, first-touch ordering of active_clients, reset placement.
Plus 300 seeded random walks. Every sequence ends with stats() +
active_clients() as the observable digest.
"""
import random

DIGEST = [("stats", ()), ("active_clients", ())]


def _seq(name, ctor, calls):
    return (name, ctor, calls + DIGEST)


def _validation_probes():
    out = []
    for bad in (0, 101, True, False, "5", 1.5, None):
        out.append((f"probe_ctor_rate_{bad!r}", (bad, 5), [("stats", ())]))
        out.append((f"probe_ctor_burst_{bad!r}", (5, bad), [("stats", ())]))
    out.append(("probe_ctor_order", (0, 0), [("stats", ())]))  # rate msg first
    out.append(_seq("probe_ctor_boundaries_low", (1, 1), [("allow", ("c",))]))
    out.append(_seq("probe_ctor_boundaries_high", (100, 100), [("allow", ("c",))]))
    bad_clients = [("",), ("x" * 65,), (7,), (None,), (True,)]
    for method in ("allow", "remaining", "reset"):
        out.append(_seq(f"probe_{method}_client", (2, 3),
                        [(method, bad) for bad in bad_clients]
                        + [(method, ("x" * 64,)), (method, ("ghost",))]))
    out.append(_seq("probe_tick_n", (2, 3), [
        ("tick", (bad,)) for bad in (0, -1, True, False, "2", 1.5, None)
    ] + [("tick", (1,)), ("tick", (99,))]))
    return out


def _deep_state_reachers():
    out = []
    out.append(_seq("deep_drain_past_zero", (1, 3), [
        ("allow", ("c",)), ("allow", ("c",)), ("allow", ("c",)),
        ("allow", ("c",)), ("allow", ("c",)),      # two denials at zero
        ("remaining", ("c",)),
    ]))
    out.append(_seq("deep_exact_refill_boundary", (2, 3), [
        ("allow", ("c",)), ("allow", ("c",)), ("allow", ("c",)),
        ("allow", ("c",)),                          # denied at zero
        ("tick", (1,)),                             # exactly +2
        ("remaining", ("c",)),
        ("allow", ("c",)), ("allow", ("c",)), ("allow", ("c",)),
    ]))
    out.append(_seq("deep_clamp_long_idle", (10, 4), [
        ("allow", ("c",)),
        ("tick", (50,)),
        ("remaining", ("c",)),                      # must clamp to burst
        ("allow", ("c",)), ("allow", ("c",)), ("allow", ("c",)),
        ("allow", ("c",)), ("allow", ("c",)),       # burst+1th must deny
    ]))
    cycle = []
    for _ in range(5):                              # repeated drain/refill cycles
        cycle += [("allow", ("c",)), ("allow", ("c",)), ("allow", ("c",)),
                  ("tick", (1,)), ("remaining", ("c",))]
    out.append(_seq("deep_drain_refill_cycles", (1, 2), cycle))
    out.append(_seq("deep_reset_in_each_state", (1, 2), [
        ("reset", ("c",)),                          # unknown -> False
        ("allow", ("c",)),
        ("reset", ("c",)),                          # partially drained
        ("remaining", ("c",)),
        ("allow", ("c",)), ("allow", ("c",)),
        ("allow", ("c",)),                          # denied
        ("reset", ("c",)),                          # drained
        ("allow", ("c",)),
        ("tick", (3,)), ("reset", ("c",)),          # after idle
        ("remaining", ("c",)),
    ]))
    out.append(_seq("deep_late_first_touch", (1, 3), [
        ("tick", (10,)),
        ("allow", ("late",)),                       # created full despite t=10
        ("remaining", ("late",)),
        ("allow", ("late",)), ("allow", ("late",)), ("allow", ("late",)),
    ]))
    return out


def _order_dependence():
    out = []
    out.append(_seq("order_allow_tick_allow", (1, 1), [
        ("allow", ("c",)), ("tick", (1,)), ("allow", ("c",)), ("allow", ("c",)),
    ]))
    out.append(_seq("order_tick_allow_allow", (1, 1), [
        ("tick", (1,)), ("allow", ("c",)), ("allow", ("c",)), ("allow", ("c",)),
    ]))
    out.append(_seq("order_first_touch_zeta_first", (1, 5), [
        ("allow", ("zeta",)), ("allow", ("alpha",)), ("allow", ("mid",)),
        ("active_clients", ()),
    ]))
    out.append(_seq("order_first_touch_alpha_first", (1, 5), [
        ("allow", ("alpha",)), ("allow", ("zeta",)), ("allow", ("mid",)),
        ("active_clients", ()),
    ]))
    out.append(_seq("order_reset_before_vs_after_drain", (1, 2), [
        ("allow", ("c",)), ("reset", ("c",)), ("allow", ("c",)), ("allow", ("c",)),
        ("allow", ("c",)),
    ]))
    out.append(_seq("order_interleaved_two_clients", (1, 2), [
        ("allow", ("a",)), ("allow", ("b",)), ("tick", (1,)),
        ("allow", ("a",)), ("allow", ("a",)), ("allow", ("a",)),
        ("allow", ("b",)), ("remaining", ("a",)), ("remaining", ("b",)),
    ]))
    return out


def _generated(n_sequences=300, seed=20260612):
    clients = ["a", "b", "c", "d", "e"]
    out = []
    for i in range(n_sequences):
        rng = random.Random(seed + i)
        ctor = (rng.randint(1, 4), rng.randint(1, 5))
        length = rng.randint(10, 80)
        calls = []
        for _ in range(length):
            r = rng.random()
            who = rng.choice(clients)
            if r < 0.35:
                calls.append(("allow", (who,)))
            elif r < 0.55:
                calls.append(("tick", (rng.randint(1, 3),)))
            elif r < 0.70:
                calls.append(("remaining", (who,)))
            elif r < 0.78:
                calls.append(("reset", (who,)))
            elif r < 0.85:
                calls.append(("active_clients", ()))
            else:
                calls.append(("stats", ()))
            if rng.random() < 0.04:
                calls.append(rng.choice([
                    ("allow", ("",)),
                    ("allow", ("y" * 65,)),
                    ("remaining", (9,)),
                    ("reset", (None,)),
                    ("tick", (0,)),
                    ("tick", (True,)),
                ]))
        out.append(_seq(f"rand-{i}", ctor, calls))
    return out


def build_corpus():
    return (_validation_probes() + _deep_state_reachers()
            + _order_dependence() + _generated())
