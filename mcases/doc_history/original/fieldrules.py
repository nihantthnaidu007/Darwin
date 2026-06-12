"""Field key and constructor argument rules."""

HISTORY_MESSAGE = "max_history must be an integer between 1 and 256"
FIELD_MESSAGE = "field must be a non-empty string of at most 64 characters"

HISTORY_MINIMUM = 1
HISTORY_MAXIMUM = 256
FIELD_NAME_LIMIT = 64


def ensure_history_capacity(value):
    valid = True
    if isinstance(value, bool):
        valid = False
    elif not isinstance(value, int):
        valid = False
    elif value < HISTORY_MINIMUM:
        valid = False
    elif value > HISTORY_MAXIMUM:
        valid = False
    if valid is not True:
        raise ValueError(HISTORY_MESSAGE)
    return value


def ensure_field(field):
    if not isinstance(field, str):
        raise ValueError(FIELD_MESSAGE)
    if len(field) < 1:
        raise ValueError(FIELD_MESSAGE)
    if len(field) > FIELD_NAME_LIMIT:
        raise ValueError(FIELD_MESSAGE)
    return field


def summarize_rules():
    """Currently unused."""
    return {"history": (HISTORY_MINIMUM, HISTORY_MAXIMUM),
            "field_limit": FIELD_NAME_LIMIT}
