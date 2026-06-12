"""P3 extracted hit/miss/eviction/expiry counters."""


class Counters:
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expired = 0

    def snapshot(self):
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expired": self.expired,
        }
