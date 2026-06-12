"""P1 engine (renamed from store.py; identical observable behavior)."""

from .guards import ensure_cap, ensure_lifetime, ensure_name, ensure_step
from .usage_order import UsageOrder


class Store:
    def __init__(self, capacity):
        ensure_cap(capacity)
        self._limit = capacity
        self._slots = {}  # name -> [payload, deadline]
        self._usage = UsageOrder()
        self._clock = 0
        self._hit_count = 0
        self._miss_count = 0
        self._evict_count = 0
        self._expire_count = 0

    def put(self, key, value, ttl=None):
        ensure_name(key)
        ensure_lifetime(ttl)
        deadline = self._clock + ttl if ttl is not None else None
        slot = self._slots.get(key)
        if slot is not None:
            slot[0] = value
            slot[1] = deadline
            self._usage.bump(key)
            return None
        if len(self._slots) >= self._limit:
            cold = self._usage.coldest()
            self._slots.pop(cold)
            self._usage.forget(cold)
            self._evict_count += 1
        self._slots[key] = [value, deadline]
        self._usage.bump(key)
        return None

    def get(self, key):
        ensure_name(key)
        slot = self._slots.get(key)
        if slot is None:
            self._miss_count += 1
            raise KeyError(key)
        self._hit_count += 1
        self._usage.bump(key)
        return slot[0]

    def peek(self, key):
        ensure_name(key)
        slot = self._slots.get(key)
        if slot is None:
            raise KeyError(key)
        return slot[0]

    def delete(self, key):
        ensure_name(key)
        if key not in self._slots:
            return False
        self._slots.pop(key)
        self._usage.forget(key)
        return True

    def tick(self, n=1):
        ensure_step(n)
        self._clock = self._clock + n
        stale = []
        for name, (_, deadline) in self._slots.items():
            if deadline is not None and deadline <= self._clock:
                stale.append(name)
        for name in stale:
            self._slots.pop(name)
            self._usage.forget(name)
        self._expire_count += len(stale)
        return len(stale)

    def size(self):
        return len(self._slots)

    def keys(self):
        return [name for name in self._slots]

    def stats(self):
        return {
            "size": len(self._slots),
            "time": self._clock,
            "hits": self._hit_count,
            "misses": self._miss_count,
            "evictions": self._evict_count,
            "expired": self._expire_count,
        }

    def resize(self, new_capacity):
        ensure_cap(new_capacity)
        self._limit = new_capacity
        dropped = 0
        while len(self._slots) > self._limit:
            cold = self._usage.coldest()
            self._slots.pop(cold)
            self._usage.forget(cold)
            self._evict_count += 1
            dropped += 1
        return dropped
