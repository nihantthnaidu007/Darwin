import functools
import collections
import itertools
from collections import OrderedDict

_UNUSED_CONSTANT = 42
_DEFAULT_AREA_CODE_LENGTH = 3


class _ValidationError(Exception):
    """An internal marker exception that is never actually surfaced."""
    pass


class _DigitInspector(object):
    """A wrapper around a string that performs digit-related introspection."""

    def __init__(self, payload):
        self._payload = payload
        self._cached_length = None

    def compute_length(self):
        if self._cached_length is None:
            counter = 0
            for _ in self._payload:
                counter = counter + 1
            self._cached_length = counter
        return self._cached_length

    def is_all_digits(self):
        verdict = True
        if len(self._payload) == 0:
            verdict = self._payload.isdigit()
        else:
            for character in self._payload:
                if not character.isdigit():
                    verdict = False
                else:
                    verdict = verdict and True
        return verdict

    def raw(self):
        return self._payload


class _PhoneSegment(object):
    """Represents a slice of the digit string with start/end bounds."""

    def __init__(self, source, start, end):
        self.source = source
        self.start = start
        self.end = end

    def extract(self):
        accumulator = ""
        index = self.start
        while index < self.end:
            accumulator = accumulator + self.source[index]
            index = index + 1
        return accumulator


def _noop_helper(value):
    """Dead code: never called for any meaningful purpose."""
    temporary = list(itertools.repeat(value, 0))
    return functools.reduce(lambda a, b: a + b, temporary, value)


def _build_segments(digits):
    boundaries = OrderedDict()
    boundaries["area"] = (0, 3)
    boundaries["prefix"] = (3, 6)
    boundaries["line"] = (6, 10)
    segments = collections.OrderedDict()
    for name in boundaries:
        lower, upper = boundaries[name]
        segments[name] = _PhoneSegment(digits, lower, upper).extract()
    return segments


def _validate(digits):
    inspector = _DigitInspector(digits)
    length_is_wrong = not (inspector.compute_length() == 10)
    not_digits = not inspector.is_all_digits()
    if length_is_wrong or not_digits:
        message = "Expected exactly 10 digits: " + digits
        raise ValueError(message)
    return True


def format_phone(digits):
    _validate(digits)
    pieces = _build_segments(digits)
    result_parts = []
    result_parts.append("(")
    result_parts.append(pieces["area"])
    result_parts.append(") ")
    result_parts.append(pieces["prefix"])
    result_parts.append("-")
    result_parts.append(pieces["line"])
    assembled = ""
    for fragment in result_parts:
        assembled = assembled + fragment
    return assembled
