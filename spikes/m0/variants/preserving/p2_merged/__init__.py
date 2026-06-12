"""P2: behavior-preserving refactor — the three modules merged into one
file; helper classes inlined into the Store body. Observable behavior
must be identical to original/."""

__all__ = ["Store"]

_CAPACITY_MSG = "capacity must be an integer between 1 and 1024"
_KEY_MSG = "key must be a non-empty string of at most 64 characters"
_TTL_MSG = "ttl must be None or a positive integer"
_TICK_MSG = "n must be a positive integer"


class Store:
    def __init__(self, capacity):
        if (not isinstance(capacity, int) or isinstance(capacity, bool)
                or capacity < 1 or capacity > 1024):
            raise ValueError(_CAPACITY_MSG)
        self._capacity = capacity
        self._data = {}        # key -> [value, expiry]; insertion order
        self._lru_order = []   # index 0 = LRU, index -1 = MRU
        self._time = 0
        self._counters = {"hits": 0, "misses": 0, "evictions": 0, "expired": 0}

    @staticmethod
    def _check_key(key):
        if not isinstance(key, str) or not 1 <= len(key) <= 64:
            raise ValueError(_KEY_MSG)

    def _touch(self, key):
        if key in self._lru_order:
            self._lru_order.remove(key)
        self._lru_order.append(key)

    def _evict_lru(self):
        victim = self._lru_order.pop(0)
        del self._data[victim]
        self._counters["evictions"] += 1

    def put(self, key, value, ttl=None):
        self._check_key(key)
        if ttl is not None and (not isinstance(ttl, int)
                                or isinstance(ttl, bool) or ttl < 1):
            raise ValueError(_TTL_MSG)
        expiry = None if ttl is None else self._time + ttl
        if key in self._data:
            self._data[key] = [value, expiry]
            self._touch(key)
            return None
        if len(self._data) >= self._capacity:
            self._evict_lru()
        self._data[key] = [value, expiry]
        self._touch(key)
        return None

    def get(self, key):
        self._check_key(key)
        if key not in self._data:
            self._counters["misses"] += 1
            raise KeyError(key)
        self._counters["hits"] += 1
        self._touch(key)
        return self._data[key][0]

    def peek(self, key):
        self._check_key(key)
        if key not in self._data:
            raise KeyError(key)
        return self._data[key][0]

    def delete(self, key):
        self._check_key(key)
        if key not in self._data:
            return False
        del self._data[key]
        self._lru_order.remove(key)
        return True

    def tick(self, n=1):
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ValueError(_TICK_MSG)
        self._time += n
        doomed = [k for k, v in self._data.items()
                  if v[1] is not None and v[1] <= self._time]
        for k in doomed:
            del self._data[k]
            self._lru_order.remove(k)
        self._counters["expired"] += len(doomed)
        return len(doomed)

    def size(self):
        return len(self._data)

    def keys(self):
        return list(self._data)

    def stats(self):
        return {
            "size": len(self._data),
            "time": self._time,
            "hits": self._counters["hits"],
            "misses": self._counters["misses"],
            "evictions": self._counters["evictions"],
            "expired": self._counters["expired"],
        }

    def resize(self, new_capacity):
        if (not isinstance(new_capacity, int) or isinstance(new_capacity, bool)
                or new_capacity < 1 or new_capacity > 1024):
            raise ValueError(_CAPACITY_MSG)
        self._capacity = new_capacity
        evicted = 0
        while len(self._data) > self._capacity:
            self._evict_lru()
            evicted += 1
        return evicted
