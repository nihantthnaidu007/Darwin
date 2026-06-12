"""Argument checking helpers."""

RATE_MESSAGE = "rate must be an integer between 1 and 100"
BURST_MESSAGE = "burst must be an integer between 1 and 100"
CLIENT_MESSAGE = "client must be a non-empty string of at most 64 characters"
TICK_MESSAGE = "n must be a positive integer"

UNIT_MINIMUM = 1
UNIT_MAXIMUM = 100
CLIENT_KEY_LIMIT = 64


def is_proper_integer(value):
    if isinstance(value, bool):
        return False
    if not isinstance(value, int):
        return False
    return True


def assert_rate(rate):
    acceptable = True
    if not is_proper_integer(rate):
        acceptable = False
    elif rate < UNIT_MINIMUM:
        acceptable = False
    elif rate > UNIT_MAXIMUM:
        acceptable = False
    if not acceptable:
        raise ValueError(RATE_MESSAGE)
    return rate


def assert_burst(burst):
    acceptable = True
    if not is_proper_integer(burst):
        acceptable = False
    elif burst < UNIT_MINIMUM:
        acceptable = False
    elif burst > UNIT_MAXIMUM:
        acceptable = False
    if not acceptable:
        raise ValueError(BURST_MESSAGE)
    return burst


def assert_client(client):
    if not isinstance(client, str):
        raise ValueError(CLIENT_MESSAGE)
    if len(client) < 1:
        raise ValueError(CLIENT_MESSAGE)
    if len(client) > CLIENT_KEY_LIMIT:
        raise ValueError(CLIENT_MESSAGE)
    return client


def assert_tick(n):
    if not is_proper_integer(n):
        raise ValueError(TICK_MESSAGE)
    if n < 1:
        raise ValueError(TICK_MESSAGE)
    return n


def describe_limits():
    """Currently unused."""
    return {"minimum": UNIT_MINIMUM, "maximum": UNIT_MAXIMUM,
            "client_key_limit": CLIENT_KEY_LIMIT}
