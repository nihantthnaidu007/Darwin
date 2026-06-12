"""Recency bookkeeping for LRU eviction.

Keeps keys ordered least-recently-used first, most-recently-used last.
Separate from the entry map on purpose: insertion order (what keys()
reports) and recency order (what eviction consults) are different state.
"""


class RecencyList:
    def __init__(self):
        self._order = []  # index 0 = LRU, index -1 = MRU

    def touch(self, key):
        """Move key to MRU position, inserting it if absent."""
        if key in self._order:
            self._order.remove(key)
        self._order.append(key)

    def discard(self, key):
        """Remove key if present."""
        if key in self._order:
            self._order.remove(key)

    def lru(self):
        """Return the least-recently-used key. Caller guarantees non-empty."""
        return self._order[0]

    def mru(self):
        return self._order[-1]
