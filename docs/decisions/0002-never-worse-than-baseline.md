# 0002 Never-worse-than-baseline

Decision: The loop returns the best gate-passing candidate found across all generations, or the baseline original if none scores strictly below it. It never returns a worse-scoring result.

Context: An optimizer that can regress is not safe to run unattended. tools/loop.py evaluates the bloated original as the baseline and the guaranteed fallback (gen 0), keeps the lowest-cost gate-passing candidate, and falls back to the original when nothing beats it.

Alternatives rejected:
- Return the last generation: a later generation can be worse than an earlier one.
- Return any improvement without a baseline floor: gives up the hard guarantee for no benefit.

Consequences: The result is never worse than the input by the structural metric. The guarantee holds even on a stochastic single run and bounds run-to-run variance.
