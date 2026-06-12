"""The Store: a capacity-bounded key-value store with LRU eviction and
TTL expiry driven by a logical clock.

Behavioral contract (every preserving refactor must match this exactly):

- Store(capacity): capacity is an int in [1, 1024] (bool rejected).
- put(key, value, ttl=None) -> None
    Existing key: update value, reset expiry from current time, move to
    MRU. Never evicts. New key: if the store is full, evict the LRU entry
    first (evictions += 1), then insert at MRU. ttl=None means no expiry;
    ttl=t means the entry expires once time >= insert_time + t.
- get(key) -> value
    Hit: hits += 1, entry moves to MRU. Miss: misses += 1, KeyError(key).
- peek(key) -> value
    Same value as get, but touches neither recency nor counters.
- delete(key) -> bool
    True if the key was present (entry removed). No counters.
- tick(n=1) -> int
    Advances the logical clock by n (int >= 1), then eagerly purges every
    entry whose expiry <= time. Returns the number purged; expired += that.
- size() -> int, keys() -> list in insertion order (a re-put of an
  existing key keeps its original position; delete + put re-inserts at
  the end).
- stats() -> {"size", "time", "hits", "misses", "evictions", "expired"}
- resize(new_capacity) -> int
    Validates like the constructor. Shrinking below the current size
    evicts LRU entries (evictions += each) until size == capacity.
    Returns the number evicted.

All validation failures raise ValueError with the exact messages in
validation.py. Missing keys raise KeyError(key).
"""

from .recency import RecencyList
from .validation import check_capacity, check_key, check_tick, check_ttl


class Store:
    def __init__(self, capacity):
        check_capacity(capacity)
        self._capacity = capacity
        self._entries = {}  # key -> [value, expiry]; dict order = insertion order
        self._recency = RecencyList()
        self._time = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expired = 0

    def put(self, key, value, ttl=None):
        check_key(key)
        check_ttl(ttl)
        expiry = None if ttl is None else self._time + ttl
        if key in self._entries:
            self._entries[key][0] = value
            self._entries[key][1] = expiry
            return None
        if len(self._entries) >= self._capacity:
            victim = self._recency.lru()
            del self._entries[victim]
            self._recency.discard(victim)
            self._evictions += 1
        self._entries[key] = [value, expiry]
        self._recency.touch(key)
        return None

    def get(self, key):
        check_key(key)
        if key not in self._entries:
            self._misses += 1
            raise KeyError(key)
        self._hits += 1
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
        del self._entries[key]
        self._recency.discard(key)
        return True

    def tick(self, n=1):
        check_tick(n)
        self._time += n
        doomed = [
            k for k, (_, expiry) in self._entries.items()
            if expiry is not None and expiry <= self._time
        ]
        for k in doomed:
            del self._entries[k]
            self._recency.discard(k)
        self._expired += len(doomed)
        return len(doomed)

    def size(self):
        return len(self._entries)

    def keys(self):
        return list(self._entries)

    def stats(self):
        return {
            "size": len(self._entries),
            "time": self._time,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "expired": self._expired,
        }

    def resize(self, new_capacity):
        check_capacity(new_capacity)
        self._capacity = new_capacity
        evicted = 0
        while len(self._entries) > self._capacity:
            victim = self._recency.lru()
            del self._entries[victim]
            self._recency.discard(victim)
            self._evictions += 1
            evicted += 1
        return evicted
