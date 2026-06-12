"""P1 argument guards (renamed from validation.py, same messages)."""

_CAP_ERR = "capacity must be an integer between 1 and 1024"
_KEY_ERR = "key must be a non-empty string of at most 64 characters"
_TTL_ERR = "ttl must be None or a positive integer"
_STEP_ERR = "n must be a positive integer"


def _fail(message):
    raise ValueError(message)


def ensure_cap(cap):
    ok = isinstance(cap, int) and not isinstance(cap, bool) and 1 <= cap <= 1024
    if not ok:
        _fail(_CAP_ERR)


def ensure_name(name):
    ok = isinstance(name, str) and 1 <= len(name) <= 64
    if not ok:
        _fail(_KEY_ERR)


def ensure_lifetime(lifetime):
    if lifetime is None:
        return
    ok = isinstance(lifetime, int) and not isinstance(lifetime, bool) and lifetime >= 1
    if not ok:
        _fail(_TTL_ERR)


def ensure_step(step):
    ok = isinstance(step, int) and not isinstance(step, bool) and step >= 1
    if not ok:
        _fail(_STEP_ERR)
