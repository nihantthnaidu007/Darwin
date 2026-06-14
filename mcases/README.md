# mcases: the multi-file case store (v3 / V0)

Ground-truth cases for multi-file optimization. Each case is a genuinely
stateful, order-dependent multi-file unit; correctness for candidates is
differential equivalence at the public API (per the M0 findings in
[reports/M0_EQUIVALENCE.md](../reports/M0_EQUIVALENCE.md)), so the
SEQUENCE CORPUS is the load-bearing artifact of every case.

Case layout:

- `original/` - working but bloated multi-file unit (the optimizer input).
- `reference/` - clean hidden version, same public API, exact same
  behavior; sets the structural-complexity floor.
- `corpus.py` - `build_corpus()` -> sequences `(name, ctor_args, calls)`.
  Hand-authored sections cover the three M0 gap classes (per-method
  validation probes for EVERY public method, deep-state reachers,
  order-dependence discriminators) plus seeded random walks for breadth.
- `test_suite.py` - strict pytest suite; `MCASE_UNIT` selects the unit.
- `breaks.py` - planted subtle behavior changes as exact-match patches.
  The corpus is proven strong by CATCHING all of them; breaks marked
  `expect_caught=False` are documented irreducible misses (M0 gap class 3:
  not observable through the API).
- `conventions.md` - comparator conventions (exception strictness, typed
  equality, determinism).
- `baseline_metrics.json` - frozen v1 metric basket aggregated across the
  unit (`tools/mcase_metrics.py`). Note: vulture flags exported public-API
  methods as unused in BOTH units (no in-package callers); the
  original-vs-reference delta is the meaningful dead-code signal.
- `meta.json` - entry symbol, public API, statefulness and bloat rationale.

Validate (from `tools/`, no Docker, no API key, no LLM):

```bash
python validate_mcase.py --all     # suite + self-eq + reference-eq + catch-test
python mcase_metrics.py <case>     # refreeze baseline_metrics.json
```

A case is valid ONLY if the catch-test passes: the reference merely
passing proves nothing about corpus strength.
