"""Refill policy abstraction."""


def clamp_to_capacity(amount, capacity):
    if amount > capacity:
        return capacity
    return amount


class RefillPolicy:
    """Linear refill strategy: rate tokens per elapsed tick, clamped."""

    def __init__(self, rate, capacity):
        self.rate = rate
        self.capacity = capacity
        self.strategy = "linear"

    def compute_gain(self, elapsed_ticks):
        if elapsed_ticks <= 0:
            return 0
        gain = self.rate * elapsed_ticks
        return gain

    def apply(self, bucket_state, current_time):
        elapsed = current_time - bucket_state.last_touched
        gain = self.compute_gain(elapsed)
        replenished = bucket_state.tokens + gain
        replenished = clamp_to_capacity(replenished, self.capacity)
        if replenished > self.capacity:
            replenished = self.capacity
        bucket_state.tokens = replenished
        bucket_state.last_touched = current_time
        return bucket_state.tokens
