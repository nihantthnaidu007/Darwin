"""Limiter facade wiring checks, the bucket registry, and refill policy."""

from .buckets import BucketRegistry
from .checks import assert_burst, assert_client, assert_rate, assert_tick
from .refill import RefillPolicy


class Limiter:
    def __init__(self, rate, burst):
        assert_rate(rate)
        assert_burst(burst)
        self.rate_per_tick = rate
        self.capacity = burst
        self.clock = 0
        self.registry = BucketRegistry()
        self.policy = RefillPolicy(rate, burst)
        self.total_allowed = 0
        self.total_denied = 0
        self.total_resets = 0

    def allow(self, client):
        assert_client(client)
        state = self.registry.lookup(client)
        if state is None:
            state = self.registry.create(client, self.capacity, self.clock)
        self.policy.apply(state, self.clock)
        if state.tokens >= 1:
            state.consume_one()
            self.total_allowed = self.total_allowed + 1
            return True
        else:
            self.total_denied = self.total_denied + 1
            return False

    def remaining(self, client):
        assert_client(client)
        state = self.registry.lookup(client)
        if state is None:
            raise KeyError(client)
        refreshed = self.policy.apply(state, self.clock)
        return refreshed

    def tick(self, n=1):
        assert_tick(n)
        updated = self.clock + n
        self.clock = updated
        return updated

    def reset(self, client):
        assert_client(client)
        state = self.registry.lookup(client)
        if state is None:
            return False
        state.tokens = self.capacity
        state.last_touched = self.clock
        self.total_resets = self.total_resets + 1
        return True

    def active_clients(self):
        return self.registry.known_clients()

    def stats(self):
        report = {}
        report["time"] = self.clock
        report["clients"] = self.registry.count()
        report["allowed"] = self.total_allowed
        report["denied"] = self.total_denied
        report["resets"] = self.total_resets
        return report
