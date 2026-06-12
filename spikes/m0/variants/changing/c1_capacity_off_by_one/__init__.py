"""M0 test subject: a small TTL+LRU key-value store.

Public API: the Store class. Everything else is internal.

This unit is genuinely stateful and order-dependent:
- get() mutates recency, so which key a later put() evicts depends on the
  full access history, not on any single call.
- peek() returns the same value as get() but does NOT touch recency or
  counters, so two sequences that differ only in get-vs-peek diverge later.
- tick() advances a logical clock and eagerly purges expired entries, so
  behavior depends on the interleaving of put() and tick().
- stats() exposes cumulative counters (hits/misses/evictions/expired),
  i.e. a digest of the entire call history.
- keys() returns insertion order, which is independent of recency order.
It is NOT a pure function in disguise: no single call has a clean
input->output contract; outputs depend on hidden state built by the
whole preceding call sequence.
"""

from .store import Store

__all__ = ["Store"]
