"""P3 extracted logical clock and expiry policy."""


class LogicalClock:
    def __init__(self):
        self.now = 0

    def advance(self, n):
        self.now += n

    def deadline_for(self, ttl):
        """Absolute expiry time for a ttl set now; None means never."""
        return None if ttl is None else self.now + ttl

    def is_expired(self, deadline):
        return deadline is not None and deadline <= self.now
