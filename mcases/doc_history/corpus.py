"""Sequence corpus for doc_history.

Gap-class coverage (per the M0 findings):
1. Unreached input subdomains -> PER-METHOD VALIDATION PROBES: constructor
   max_history, and field-key probes on set/remove/get (invalid, boundary
   invalid, boundary valid, unknown). Argless methods (undo/redo/fields/
   depth/stats) probed in empty and exhausted states.
2. Unreached deep states -> DEEP-STATE REACHERS: undo chains through the
   history cap at several capacities, full undo-to-empty then redo-to-full
   ladders, cap-1 stores, long mutation runs.
3. Order dependence -> redo-cleared-by-set discriminator, no-op-remove
   discriminator (must NOT clear redo), overwrite-undo position probes,
   remove-undo end-reinsertion probes, permuted op orders.
Plus 300 seeded random walks. Every sequence ends with stats() + fields()
+ depth() as the observable digest.
"""
import random

DIGEST = [("stats", ()), ("fields", ()), ("depth", ())]


def _seq(name, ctor, calls):
    return (name, ctor, calls + DIGEST)


def _validation_probes():
    out = []
    for bad in (0, 257, True, False, "5", 1.5, None):
        out.append((f"probe_ctor_{bad!r}", (bad,), [("stats", ())]))
    out.append(_seq("probe_ctor_boundaries", (1,), [("set", ("a", 1))]))
    out.append(_seq("probe_ctor_boundary_high", (256,), [("set", ("a", 1))]))
    bad_fields = [("",), ("x" * 65,), (7,), (None,), (True,)]
    out.append(_seq("probe_set_field", (4,),
                    [("set", bad + (1,)) for bad in bad_fields]
                    + [("set", ("x" * 64, "v")), ("get", ("x" * 64,))]))
    for method in ("remove", "get"):
        out.append(_seq(f"probe_{method}_field", (4,),
                        [(method, bad) for bad in bad_fields]
                        + [(method, ("ghost",))]))
    out.append(_seq("probe_argless_empty", (4,), [
        ("undo", ()), ("redo", ()), ("fields", ()), ("depth", ()), ("stats", ()),
        ("undo", ()), ("redo", ()),
    ]))
    return out


def _deep_state_reachers():
    out = []
    for cap in (1, 2, 3):
        calls = [("set", (f"f{i}", i)) for i in range(cap + 2)]
        calls += [("undo", ()) for _ in range(cap + 2)]   # past the cap floor
        calls += [("redo", ()) for _ in range(cap + 2)]
        out.append(_seq(f"deep_cap_boundary_{cap}", (cap,), calls))
    ladder = [("set", ("a", 1)), ("set", ("b", 2)), ("remove", ("a",)),
              ("set", ("c", 3)), ("set", ("b", 9))]
    ladder += [("undo", ()) for _ in range(6)]
    ladder += [("redo", ()) for _ in range(6)]
    out.append(_seq("deep_full_round_trip", (10,), ladder))
    out.append(_seq("deep_interleaved_undo_redo", (10,), [
        ("set", ("a", 1)), ("set", ("a", 2)), ("set", ("a", 3)),
        ("undo", ()), ("redo", ()), ("undo", ()), ("undo", ()),
        ("get", ("a",)), ("redo", ()), ("get", ("a",)),
        ("set", ("a", 9)),                  # clears remaining redo
        ("redo", ()), ("get", ("a",)),
    ]))
    long_run = []
    for i in range(40):                     # far past cap 5
        long_run.append(("set", ("k", i)) if i % 3 else ("set", (f"f{i}", i)))
    long_run += [("undo", ()) for _ in range(7)]
    out.append(_seq("deep_long_run_cap5", (5,), long_run))
    return out


def _order_dependence():
    out = []
    out.append(_seq("order_set_clears_redo", (8,), [
        ("set", ("a", 1)), ("set", ("a", 2)), ("undo", ()),
        ("set", ("a", 5)),
        ("redo", ()), ("get", ("a",)),
    ]))
    out.append(_seq("order_noop_remove_keeps_redo", (8,), [
        ("set", ("a", 1)), ("undo", ()),
        ("remove", ("ghost",)),             # no-op: redo must survive
        ("redo", ()), ("get", ("a",)),
    ]))
    out.append(_seq("order_real_remove_clears_redo", (8,), [
        ("set", ("a", 1)), ("set", ("b", 2)), ("undo", ()),
        ("remove", ("a",)),                 # real: redo must die
        ("redo", ()), ("fields", ()),
    ]))
    out.append(_seq("order_undo_overwrite_position", (8,), [
        ("set", ("a", 1)), ("set", ("b", 2)), ("set", ("c", 3)),
        ("set", ("a", 9)),                  # overwrite first field
        ("undo", ()),
        ("fields", ()), ("get", ("a",)),
    ]))
    out.append(_seq("order_undo_remove_position", (8,), [
        ("set", ("a", 1)), ("set", ("b", 2)), ("set", ("c", 3)),
        ("remove", ("a",)), ("undo", ()),
        ("fields", ()),
    ]))
    out.append(_seq("order_same_ops_different_order_1", (8,), [
        ("set", ("a", 1)), ("remove", ("a",)), ("set", ("a", 2)),
        ("undo", ()), ("fields", ()),
    ]))
    out.append(_seq("order_same_ops_different_order_2", (8,), [
        ("set", ("a", 2)), ("set", ("a", 1)), ("remove", ("a",)),
        ("undo", ()), ("fields", ()), ("get", ("a",)),
    ]))
    return out


def _generated(n_sequences=300, seed=20260612):
    fields = ["a", "b", "c", "d"]
    values = [0, 1, 7, "v", None, -2]
    out = []
    for i in range(n_sequences):
        rng = random.Random(seed + i)
        ctor = (rng.randint(1, 4),)          # small caps keep the cap reachable
        length = rng.randint(10, 80)
        calls = []
        for _ in range(length):
            r = rng.random()
            f = rng.choice(fields)
            if r < 0.30:
                calls.append(("set", (f, rng.choice(values))))
            elif r < 0.42:
                calls.append(("remove", (f,)))
            elif r < 0.54:
                calls.append(("get", (f,)))
            elif r < 0.69:
                calls.append(("undo", ()))
            elif r < 0.81:
                calls.append(("redo", ()))
            elif r < 0.89:
                calls.append(("fields", ()))
            elif r < 0.95:
                calls.append(("depth", ()))
            else:
                calls.append(("stats", ()))
            if rng.random() < 0.04:
                calls.append(rng.choice([
                    ("set", ("", 1)),
                    ("set", ("y" * 65, 1)),
                    ("remove", (4,)),
                    ("get", (None,)),
                    ("get", (True,)),
                ]))
        out.append(_seq(f"rand-{i}", ctor, calls))
    return out


def build_corpus():
    return (_validation_probes() + _deep_state_reachers()
            + _order_dependence() + _generated())
