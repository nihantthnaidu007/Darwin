"""P4 store on different data structures (OrderedDict recency, Entry objects)."""

from collections import OrderedDict

from .validation import check_capacity, check_key, check_tick, check_ttl


class Entry:
    __slots__ = ("value", "expiry")

    def __init__(self, value, expiry):
        self.value = value
        self.expiry = expiry


class Store:
    def __init__(self, capacity):
        check_capacity(capacity)
        self._capacity = capacity
        self._entries = {}            # key -> Entry; dict order = insertion order
        self._recency = OrderedDict() # first = LRU, last = MRU (values unused)
        self._time = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expired = 0

    def _touch(self, key):
        if key in self._recency:
            self._recency.move_to_end(key)
        else:
            self._recency[key] = True

    def _remove(self, key):
        del self._entries[key]
        self._recency.pop(key, None)

    def _evict_one(self):
        victim = next(iter(self._recency))
        self._remove(victim)
        self._evictions += 1

    def put(self, key, value, ttl=None):
        check_key(key)
        check_ttl(ttl)
        expiry = None if ttl is None else self._time + ttl
        entry = self._entries.get(key)
        if entry is not None:
            entry.value = value
            entry.expiry = expiry
            self._touch(key)
            return None
        if len(self._entries) >= self._capacity:
            self._evict_one()
        self._entries[key] = Entry(value, expiry)
        self._touch(key)
        return None

    def get(self, key):
        check_key(key)
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            raise KeyError(key)
        self._hits += 1
        self._touch(key)
        return entry.value

    def peek(self, key):
        check_key(key)
        entry = self._entries.get(key)
        if entry is None:
            raise KeyError(key)
        return entry.value

    def delete(self, key):
        check_key(key)
        if key not in self._entries:
            return False
        self._remove(key)
        return True

    def tick(self, n=1):
        check_tick(n)
        self._time += n
        doomed = [k for k, e in self._entries.items()
                  if e.expiry is not None and e.expiry <= self._time]
        for k in doomed:
            self._remove(k)
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
            self._evict_one()
            evicted += 1
        return evicted
