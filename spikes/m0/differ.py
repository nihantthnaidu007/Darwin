"""M0 differential equivalence check at the public API.

Treats a multi-file unit as a black box exporting Store. Equivalence is
defined as: for every generated SEQUENCE of public-API calls, the original
and the candidate produce identical per-call observable outputs, where an
observable output is the return value, or the raised exception's type name
and message. A fresh instance is used per sequence. Private internals are
never inspected.

The verdict is therefore relative to two things, stated honestly:
1. the generated input domain (key pool, value pool, ttl/tick/capacity
   ranges, plus scripted boundary probes), and
2. what the API exposes. Effects invisible through the API (memory
   retention, timing, ordering of internal operations) are out of scope
   by construction.
"""

import importlib.util
import random
import sys
from pathlib import Path

# ---------------------------------------------------------------- loading

_LOAD_COUNT = 0


def load_unit(pkg_dir):
    """Import a variant directory as a uniquely named package."""
    global _LOAD_COUNT
    _LOAD_COUNT += 1
    alias = f"m0_unit_{_LOAD_COUNT}"
    init = Path(pkg_dir) / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        alias, init, submodule_search_locations=[str(pkg_dir)]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------- input generation

KEY_POOL = ["alpha", "beta", "gamma", "delta", "eps", "zeta", "k1", "k2"]
VALUE_POOL = [0, 1, 2, 7, 42, "v0", "v1", "hello", None, -3]
SEED = 20260612


def _scripted_scenarios():
    """Hand-designed boundary scenarios. Each: (name, ctor_arg, calls)."""
    K64 = "x" * 64
    K65 = "x" * 65
    s = []

    s.append(("fill_exact", 3, [
        ("put", ("a", 1)), ("put", ("b", 2)), ("put", ("c", 3)),
        ("keys", ()), ("size", ()), ("stats", ()),
    ]))
    s.append(("overfill_by_one", 3, [
        ("put", ("a", 1)), ("put", ("b", 2)), ("put", ("c", 3)),
        ("put", ("d", 4)),
        ("keys", ()), ("size", ()),
        ("get", ("a",)), ("get", ("b",)), ("get", ("c",)), ("get", ("d",)),
        ("stats", ()),
    ]))
    s.append(("get_refresh_then_evict", 2, [
        ("put", ("a", 1)), ("put", ("b", 2)),
        ("get", ("a",)),
        ("put", ("c", 3)),
        ("keys", ()), ("get", ("a",)), ("get", ("b",)), ("stats", ()),
    ]))
    s.append(("peek_no_refresh_then_evict", 2, [
        ("put", ("a", 1)), ("put", ("b", 2)),
        ("peek", ("a",)),
        ("put", ("c", 3)),
        ("keys", ()), ("get", ("a",)), ("get", ("b",)), ("stats", ()),
    ]))
    s.append(("update_refresh_then_evict", 2, [
        ("put", ("a", 1)), ("put", ("b", 2)),
        ("put", ("a", 9)),
        ("put", ("c", 3)),
        ("keys", ()), ("get", ("a",)), ("get", ("b",)), ("stats", ()),
    ]))
    s.append(("ttl_exact_boundary", 4, [
        ("put", ("x", "v"), {"ttl": 2}),
        ("tick", (1,)), ("peek", ("x",)),
        ("tick", (1,)), ("peek", ("x",)),
        ("stats", ()),
    ]))
    s.append(("ttl_purge_count", 4, [
        ("put", ("a", 1), {"ttl": 1}),
        ("put", ("b", 2), {"ttl": 2}),
        ("put", ("c", 3), {"ttl": 2}),
        ("tick", (2,)),
        ("keys", ()), ("stats", ()),
    ]))
    s.append(("validation_probes", 1, [
        ("put", ("", 1)),
        ("put", (K65, 1)),
        ("put", (K64, 1)),
        ("get", (K64,)),
        ("put", ("a", 1), {"ttl": 0}),
        ("put", ("a", 1), {"ttl": True}),
        ("tick", (0,)),
        ("get", (7,)),
        ("resize", (0,)),
        ("resize", (2000,)),
        ("stats", ()), ("keys", ()),
    ]))
    s.append(("resize_shrink_order", 4, [
        ("put", ("a", 1)), ("put", ("b", 2)), ("put", ("c", 3)), ("put", ("d", 4)),
        ("get", ("a",)), ("get", ("b",)),
        ("resize", (2,)),
        ("keys", ()), ("get", ("a",)), ("get", ("c",)), ("stats", ()),
    ]))
    s.append(("delete_reinsert_order", 3, [
        ("put", ("a", 1)), ("put", ("b", 2)), ("put", ("c", 3)),
        ("delete", ("b",)), ("put", ("b", 9)),
        ("keys", ()), ("stats", ()),
    ]))
    s.append(("resize_grow_no_evict", 2, [
        ("put", ("a", 1)), ("put", ("b", 2)),
        ("resize", (5,)),
        ("put", ("c", 3)), ("put", ("d", 4)), ("put", ("e", 5)),
        ("keys", ()), ("stats", ()),
    ]))
    s.append(("update_keeps_insertion_order", 3, [
        ("put", ("a", 1)), ("put", ("b", 2)), ("put", ("c", 3)),
        ("put", ("b", 9)),
        ("keys", ()),
        ("put", ("d", 4)),
        ("keys", ()), ("stats", ()),
    ]))
    s.append(("miss_and_delete_counters", 2, [
        ("get", ("nope",)), ("peek", ("nope",)), ("delete", ("nope",)),
        ("put", ("a", 1)), ("delete", ("a",)), ("delete", ("a",)),
        ("stats", ()),
    ]))
    s.append(("eviction_chain_capacity_1", 1, [
        ("put", ("a", 1)), ("put", ("b", 2)), ("put", ("c", 3)),
        ("get", ("c",)), ("get", ("a",)),
        ("keys", ()), ("stats", ()),
    ]))
    for bad in [0, 1025, True, "8", None]:
        s.append((f"constructor_probe_{bad!r}", bad, [("size", ())]))
    return s


def _random_sequences(n_sequences, seed):
    """Seeded random call sequences over a small, collision-heavy domain."""
    out = []
    for i in range(n_sequences):
        rng = random.Random(seed + i)
        capacity = rng.randint(1, 6)
        length = rng.randint(10, 120)
        calls = []
        for _ in range(length):
            r = rng.random()
            key = rng.choice(KEY_POOL)
            if r < 0.34:
                kwargs = {}
                if rng.random() < 0.45:
                    kwargs["ttl"] = rng.randint(1, 5)
                calls.append(("put", (key, rng.choice(VALUE_POOL)), kwargs))
            elif r < 0.56:
                calls.append(("get", (key,)))
            elif r < 0.64:
                calls.append(("peek", (key,)))
            elif r < 0.74:
                calls.append(("delete", (key,)))
            elif r < 0.86:
                calls.append(("tick", (rng.randint(1, 4),)))
            elif r < 0.91:
                calls.append(("stats", ()))
            elif r < 0.95:
                calls.append(("keys", ()))
            elif r < 0.98:
                calls.append(("size", ()))
            else:
                calls.append(("resize", (rng.randint(1, 6),)))
            # occasional invalid-argument probe
            if rng.random() < 0.04:
                calls.append(rng.choice([
                    ("put", ("", 0)),
                    ("put", ("y" * 65, 0)),
                    ("put", (key, 0), {"ttl": 0}),
                    ("tick", (0,)),
                    ("get", (12,)),
                    ("resize", (0,)),
                ]))
        # end every sequence with a full observable-state digest
        calls.append(("stats", ()))
        calls.append(("keys", ()))
        out.append((f"rand-{i}", capacity, calls))
    return out


def build_sequences(n_random=400, seed=SEED):
    return _scripted_scenarios() + _random_sequences(n_random, seed)


# ------------------------------------------------------------- execution

def _outcome(fn, args, kwargs):
    try:
        return ("ok", fn(*args, **kwargs))
    except Exception as e:  # exception type + message are the observable
        return ("raise", type(e).__name__, str(e))


def run_sequence(store_cls, ctor_arg, calls):
    """Run one sequence on a fresh instance; return per-call outcomes."""
    outcomes = []
    ctor = _outcome(store_cls, (ctor_arg,), {})
    outcomes.append(("__init__", ctor))
    if ctor[0] == "raise":
        return outcomes  # no instance to continue with
    instance = ctor[1]
    outcomes[0] = ("__init__", ("ok", "<store>"))  # instance itself is not a value
    for call in calls:
        method, args = call[0], call[1]
        kwargs = call[2] if len(call) > 2 else {}
        outcomes.append((method, _outcome(getattr(instance, method), args, kwargs)))
    return outcomes


def check_equivalence(original_dir, candidate_dir, sequences):
    """Differential verdict. Returns (equivalent, witness, stats_dict)."""
    orig_store = load_unit(original_dir).Store
    cand_store = load_unit(candidate_dir).Store
    calls_compared = 0
    for name, ctor_arg, calls in sequences:
        a = run_sequence(orig_store, ctor_arg, calls)
        b = run_sequence(cand_store, ctor_arg, calls)
        for idx in range(max(len(a), len(b))):
            oa = a[idx] if idx < len(a) else ("<absent>", None)
            ob = b[idx] if idx < len(b) else ("<absent>", None)
            calls_compared += 1
            if oa != ob:
                witness = {
                    "sequence": name,
                    "call_index": idx,
                    "call": "__init__" if idx == 0 else repr(calls[idx - 1]),
                    "original": oa[1],
                    "candidate": ob[1],
                }
                return False, witness, {"calls_compared": calls_compared,
                                        "sequences": len(sequences)}
    return True, None, {"calls_compared": calls_compared,
                        "sequences": len(sequences)}
