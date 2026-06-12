"""P3 validation (same messages as original)."""

CAPACITY_MSG = "capacity must be an integer between 1 and 1024"
KEY_MSG = "key must be a non-empty string of at most 64 characters"
TTL_MSG = "ttl must be None or a positive integer"
TICK_MSG = "n must be a positive integer"


def _is_real_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def check_capacity(capacity):
    if not _is_real_int(capacity) or not 1 <= capacity <= 1024:
        raise ValueError(CAPACITY_MSG)


def check_key(key):
    if not isinstance(key, str) or not 1 <= len(key) <= 64:
        raise ValueError(KEY_MSG)


def check_ttl(ttl):
    if ttl is not None and (not _is_real_int(ttl) or ttl < 1):
        raise ValueError(TTL_MSG)


def check_tick(n):
    if not _is_real_int(n) or n < 1:
        raise ValueError(TICK_MSG)
