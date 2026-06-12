"""P4 validation (same messages as original)."""

CAPACITY_MSG = "capacity must be an integer between 1 and 1024"
KEY_MSG = "key must be a non-empty string of at most 64 characters"
TTL_MSG = "ttl must be None or a positive integer"
TICK_MSG = "n must be a positive integer"


def check_capacity(capacity):
    if not isinstance(capacity, int) or isinstance(capacity, bool) \
            or capacity < 1 or capacity > 1024:
        raise ValueError(CAPACITY_MSG)


def check_key(key):
    if not isinstance(key, str) or len(key) < 1 or len(key) > 64:
        raise ValueError(KEY_MSG)


def check_ttl(ttl):
    if ttl is None:
        return
    if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl < 1:
        raise ValueError(TTL_MSG)


def check_tick(n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError(TICK_MSG)
