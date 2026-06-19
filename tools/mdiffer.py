"""Differential equivalence check for multi-file units at the public API.

Provenance: the generic core of spikes/m0/differ.py (the M0 research spike),
promoted for the V0 multi-file case store. Generalized in exactly two ways,
neither a rewrite:
1. Constructor arguments are a tuple (M0 hardcoded a single argument).
2. Equality is strict TYPED equality via canon(): M0 documented that plain
   `==` treats True as 1; canon() closes that edge. Dict key order remains
   non-observable (documented convention).

Equivalence semantics are unchanged from M0: a unit is a black box package
exporting its public class; for every sequence of API calls, original and
candidate must produce identical per-call observables (return value, or
exception type name + message) on fresh instances. Private internals are
never inspected.
"""

import importlib.util
import sys
import uuid
from pathlib import Path

# ---------------------------------------------------------------- loading


def load_unit(pkg_dir):
    """Import a unit directory as a uniquely named package."""
    # Unique per call with NO shared counter: a uuid is collision-free without
    # coordination, so concurrent loads cannot collide on a sys.modules name
    # (decision 0024). The module is still registered in sys.modules as before.
    alias = f"mcase_unit_{uuid.uuid4().hex}"
    init = Path(pkg_dir) / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        alias, init, submodule_search_locations=[str(pkg_dir)]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------ comparison


def canon(v):
    """Canonical form for strict typed comparison of observable values.

    bool and int canonicalize differently (True != 1 here, unlike `==`).
    Lists/tuples stay ordered; dicts compare order-insensitively.
    """
    if isinstance(v, bool):
        return ("bool", v)
    if isinstance(v, int):
        return ("int", v)
    if isinstance(v, float):
        return ("float", repr(v))
    if isinstance(v, str):
        return ("str", v)
    if v is None:
        return ("none",)
    if isinstance(v, (list, tuple)):
        return ("seq", tuple(canon(x) for x in v))
    if isinstance(v, dict):
        return ("dict", tuple(sorted((canon(k), canon(val)) for k, val in v.items())))
    return ("other", type(v).__name__, repr(v))


def canon_outcome(outcome):
    if outcome[0] == "ok":
        return ("ok", canon(outcome[1]))
    return outcome  # ("raise", type_name, message) is already canonical


# ------------------------------------------------------------- execution


def _outcome(fn, args, kwargs):
    try:
        return ("ok", fn(*args, **kwargs))
    except Exception as e:  # exception type + message are the observable
        return ("raise", type(e).__name__, str(e))


def run_sequence(unit_cls, ctor_args, calls):
    """Run one sequence on a fresh instance; return per-call outcomes."""
    outcomes = []
    ctor = _outcome(unit_cls, tuple(ctor_args), {})
    outcomes.append(("__init__", ctor))
    if ctor[0] == "raise":
        return outcomes  # no instance to continue with
    instance = ctor[1]
    outcomes[0] = ("__init__", ("ok", "<instance>"))
    for call in calls:
        method, args = call[0], call[1]
        kwargs = call[2] if len(call) > 2 else {}
        outcomes.append((method, _outcome(getattr(instance, method), args, kwargs)))
    return outcomes


def check_equivalence(original_dir, candidate_dir, sequences, entry="Store"):
    """Differential verdict. Returns (equivalent, witness, stats_dict).

    sequences: iterable of (name, ctor_args, calls) where calls are
    (method, args) or (method, args, kwargs) tuples.
    entry: name of the public class exported by the unit package.
    """
    orig_cls = getattr(load_unit(original_dir), entry)
    cand_cls = getattr(load_unit(candidate_dir), entry)
    calls_compared = 0
    for name, ctor_args, calls in sequences:
        a = run_sequence(orig_cls, ctor_args, calls)
        b = run_sequence(cand_cls, ctor_args, calls)
        for idx in range(max(len(a), len(b))):
            oa = a[idx] if idx < len(a) else ("<absent>", ("<absent>",))
            ob = b[idx] if idx < len(b) else ("<absent>", ("<absent>",))
            calls_compared += 1
            if oa[0] != ob[0] or canon_outcome(oa[1]) != canon_outcome(ob[1]):
                witness = {
                    "sequence": name,
                    "call_index": idx,
                    "call": "__init__" if idx == 0 else repr(calls[idx - 1]),
                    "original": oa[1],
                    "candidate": ob[1],
                }
                return (
                    False,
                    witness,
                    {"calls_compared": calls_compared, "sequences": len(sequences)},
                )
    return True, None, {"calls_compared": calls_compared, "sequences": len(sequences)}
