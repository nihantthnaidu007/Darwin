"""P3 recency tracking (same semantics as original RecencyList)."""


class RecencyList:
    def __init__(self):
        self._order = []

    def touch(self, key):
        if key in self._order:
            self._order.remove(key)
        self._order.append(key)

    def discard(self, key):
        if key in self._order:
            self._order.remove(key)

    def lru(self):
        return self._order[0]
