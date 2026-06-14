"""Token-bucket rate limiter on a logical clock. Behavioral contract.

- Limiter(rate, burst): rate is tokens refilled per tick, burst the bucket
  cap. Both must be int (bool rejected) in [1, 100], validated in that
  order, else ValueError("rate must be an integer between 1 and 100") /
  ValueError("burst must be an integer between 1 and 100").
- Client keys everywhere: non-empty str of at most 64 chars, else
  ValueError("client must be a non-empty string of at most 64 characters").
- A client's bucket is created on its FIRST allow(), full (burst tokens).
  Refill is lazy: when a bucket is touched (allow/remaining), it gains
  rate * elapsed_ticks tokens, clamped to burst, and remembers the touch
  time.
- allow(client) -> bool: refill, then consume 1 token if tokens >= 1
  (allowed += 1, True) else denied += 1, False.
- remaining(client) -> int: KeyError(client) for unknown clients; refills,
  returns the current token count. Does not consume.
- tick(n=1) -> int: n must be int (bool rejected) >= 1, else
  ValueError("n must be a positive integer"). Advances the clock, returns
  the new time.
- reset(client) -> bool: unknown client returns False; otherwise the
  bucket refills to burst (resets += 1, True).
- active_clients() -> list of known clients in first-allow order.
- stats() -> {"time", "clients", "allowed", "denied", "resets"}.

Deterministic: logical clock only, no wall time, no randomness.
"""

_RATE_MSG = "rate must be an integer between 1 and 100"
_BURST_MSG = "burst must be an integer between 1 and 100"
_CLIENT_MSG = "client must be a non-empty string of at most 64 characters"
_TICK_MSG = "n must be a positive integer"


def _check_unit_range(value, message):
    if not isinstance(value, int) or isinstance(value, bool) \
            or not 1 <= value <= 100:
        raise ValueError(message)


def _check_client(client):
    if not isinstance(client, str) or not 1 <= len(client) <= 64:
        raise ValueError(_CLIENT_MSG)


class Limiter:
    def __init__(self, rate, burst):
        _check_unit_range(rate, _RATE_MSG)
        _check_unit_range(burst, _BURST_MSG)
        self._rate = rate
        self._burst = burst
        self._time = 0
        self._buckets = {}  # client -> {"tokens": int, "last": int}
        self._allowed = 0
        self._denied = 0
        self._resets = 0

    def _refill(self, bucket):
        elapsed = self._time - bucket["last"]
        bucket["tokens"] = min(self._burst,
                               bucket["tokens"] + self._rate * elapsed)
        bucket["last"] = self._time

    def allow(self, client):
        _check_client(client)
        bucket = self._buckets.get(client)
        if bucket is None:
            bucket = {"tokens": self._burst, "last": self._time}
            self._buckets[client] = bucket
        self._refill(bucket)
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            self._allowed += 1
            return True
        self._denied += 1
        return False

    def remaining(self, client):
        _check_client(client)
        bucket = self._buckets.get(client)
        if bucket is None:
            raise KeyError(client)
        self._refill(bucket)
        return bucket["tokens"]

    def tick(self, n=1):
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ValueError(_TICK_MSG)
        self._time += n
        return self._time

    def reset(self, client):
        _check_client(client)
        bucket = self._buckets.get(client)
        if bucket is None:
            return False
        bucket["tokens"] = self._burst
        bucket["last"] = self._time
        self._resets += 1
        return True

    def active_clients(self):
        return list(self._buckets)

    def stats(self):
        return {
            "time": self._time,
            "clients": len(self._buckets),
            "allowed": self._allowed,
            "denied": self._denied,
            "resets": self._resets,
        }
