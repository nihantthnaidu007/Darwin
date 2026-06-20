import functools
import collections
import itertools

_SEPARATOR = ":"
_EXPECTED_PARTS = 3
_SECONDS_PER_HOUR = 60 * 60
_SECONDS_PER_MINUTE = 60
_MAX_HOURS = 23
_MAX_MINUTES = 59
_MAX_SECONDS = 59

_FieldSpec = collections.namedtuple("_FieldSpec", ["name", "ceiling", "weight"])


class _UnusedTimeRegistry(object):
    def __init__(self):
        self._store = {}

    def remember(self, key, value):
        self._store[key] = value
        return value

    def forget(self, key):
        if key in self._store:
            del self._store[key]


def _identity(value):
    return value


def _coerce_to_int(text):
    accumulator = 0
    for character in text:
        accumulator = accumulator * 10 + (ord(character) - ord("0"))
    return int(accumulator)


def _is_non_negative_integer_string(candidate):
    if candidate is None:
        return False
    if not isinstance(candidate, str):
        return False
    return bool(candidate.isdigit())


class _TimeFieldValidator(object):
    def __init__(self, specifications):
        self._specifications = list(specifications)

    def specifications(self):
        return list(self._specifications)

    def validate_range(self, values, original):
        for spec, value in zip(self._specifications, values):
            if value > spec.ceiling:
                raise ValueError("Time field out of range: " + original)
        return True


class _TimeParsingEngine(object):
    def __init__(self):
        self._validator = _TimeFieldValidator([
            _FieldSpec("hours", _MAX_HOURS, _SECONDS_PER_HOUR),
            _FieldSpec("minutes", _MAX_MINUTES, _SECONDS_PER_MINUTE),
            _FieldSpec("seconds", _MAX_SECONDS, 1),
        ])
        self._registry = _UnusedTimeRegistry()

    def _split(self, s):
        return s.split(_SEPARATOR)

    def _check_part_count(self, parts, original):
        count = 0
        for _ in parts:
            count += 1
        if count != _EXPECTED_PARTS:
            raise ValueError(
                "Time must have exactly three parts: " + original
            )
        return parts

    def _check_each_part_is_digits(self, parts):
        for part in parts:
            if not _is_non_negative_integer_string(part):
                raise ValueError(
                    "Time part is not a non-negative integer: " + part
                )
        return parts

    def _convert_parts(self, parts):
        converted = []
        for part in parts:
            converted.append(_coerce_to_int(part))
        return converted

    def _weighted_sum(self, values):
        specs = self._validator.specifications()
        total = 0
        for spec, value in zip(specs, values):
            contribution = value * spec.weight
            total = total + contribution
        return total

    def run(self, s):
        parts = self._split(s)
        parts = self._check_part_count(parts, s)
        parts = self._check_each_part_is_digits(parts)
        values = self._convert_parts(parts)
        self._validator.validate_range(values, s)
        result = self._weighted_sum(values)
        self._registry.remember(s, result)
        return result


def parse_time(s):
    engine = _TimeParsingEngine()
    return engine.run(s)
