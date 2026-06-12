"""P3 store composed from extracted clock/counters/recency/checks."""

from .checks import check_capacity, check_key, check_tick, check_ttl
from .clock import LogicalClock
from .counters import Counters
from .recency import RecencyList


class Store:
    def __init__(self, capacity):
        check_capacity(capacity)
        self._capacity = capacity
        self._entries = {}
        self._recency = RecencyList()
        self._clock = LogicalClock()
        self._counters = Counters()

    def _drop(self, key):
        del self._entries[key]
        self._recency.discard(key)

    def put(self, key, value, ttl=None):
        check_key(key)
        check_ttl(ttl)
        deadline = self._clock.deadline_for(ttl)
        if key in self._entries:
            entry = self._entries[key]
            entry[0] = value
            entry[1] = deadline
            self._recency.touch(key)
            return None
        if len(self._entries) >= self._capacity:
            self._drop(self._recency.lru())
            self._counters.evictions += 1
        self._entries[key] = [value, deadline]
        self._recency.touch(key)
        return None

    def get(self, key):
        check_key(key)
        if key not in self._entries:
            self._counters.misses += 1
            raise KeyError(key)
        self._counters.hits += 1
        self._recency.touch(key)
        return self._entries[key][0]

    def peek(self, key):
        check_key(key)
        if key not in self._entries:
            raise KeyError(key)
        return self._entries[key][0]

    def delete(self, key):
        check_key(key)
        if key not in self._entries:
            return False
        self._drop(key)
        return True

    def tick(self, n=1):
        check_tick(n)
        self._clock.advance(n)
        doomed = [k for k, (_, deadline) in self._entries.items()
                  if self._clock.is_expired(deadline)]
        for k in doomed:
            self._drop(k)
        self._counters.expired += len(doomed)
        return len(doomed)

    def size(self):
        return len(self._entries)

    def keys(self):
        return list(self._entries)

    def stats(self):
        out = {"size": len(self._entries), "time": self._clock.now}
        out.update(self._counters.snapshot())
        return out

    def resize(self, new_capacity):
        check_capacity(new_capacity)
        self._capacity = new_capacity
        evicted = 0
        while len(self._entries) > self._capacity:
            self._drop(self._recency.lru())
            self._counters.evictions += 1
            evicted += 1
        return evicted
