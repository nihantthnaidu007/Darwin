import functools
import collections
import itertools
import math


_SEPARATOR_TOKEN = ":"
_EXPECTED_PART_COUNT = 3
_SECONDS_PER_HOUR = 60 * 60
_SECONDS_PER_MINUTE = 60
_UNUSED_CONSTANT = 42


class _ValidationError(Exception):
    """Internal marker exception, never actually surfaced."""
    pass


def _identity(x):
    return x


def _compose(*funcs):
    def _inner(value):
        result = value
        for fn in reversed(funcs):
            result = fn(result)
        return result
    return _inner


class _Bound(object):
    def __init__(self, maximum):
        self._maximum = maximum

    @property
    def maximum(self):
        return self._maximum

    def violated_by(self, candidate):
        if candidate > self._maximum:
            return True
        else:
            return False


class _FieldDescriptor(object):
    def __init__(self, name, bound):
        self.name = name
        self.bound = bound

    def check(self, value):
        return not self.bound.violated_by(value)


def _split_into_parts(raw):
    accumulated = []
    for chunk in raw.split(_SEPARATOR_TOKEN):
        accumulated.append(chunk)
    return accumulated


def _all_digits(token):
    verdict = True
    if not token.isdigit():
        verdict = False
    else:
        verdict = True
    return verdict


def _coerce(token):
    return int(token)


class _TimeAssembler(object):
    def __init__(self):
        self.descriptors = [
            _FieldDescriptor("hours", _Bound(23)),
            _FieldDescriptor("minutes", _Bound(59)),
            _FieldDescriptor("seconds", _Bound(59)),
        ]

    def validate_count(self, parts, original):
        count = 0
        for _ in parts:
            count += 1
        if count != _EXPECTED_PART_COUNT:
            raise ValueError(
                "Time must have exactly three parts: " + original
            )
        return parts

    def validate_digits(self, parts):
        for part in parts:
            digit_ok = _all_digits(part)
            if not digit_ok:
                raise ValueError(
                    "Time part is not a non-negative integer: " + part
                )
        return parts

    def validate_ranges(self, values, original):
        descriptor_iter = iter(self.descriptors)
        for value in values:
            descriptor = next(descriptor_iter)
            if not descriptor.check(value):
                raise ValueError("Time field out of range: " + original)
        return values

    def assemble(self, values):
        h, m, sec = values[0], values[1], values[2]
        total = 0
        total += h * _SECONDS_PER_HOUR
        total += m * _SECONDS_PER_MINUTE
        total += sec
        return total


def parse_time(s):
    assembler = _TimeAssembler()
    parts = _split_into_parts(s)
    parts = assembler.validate_count(parts, s)
    parts = assembler.validate_digits(parts)

    numeric_values = []
    for token in parts:
        numeric_values.append(_coerce(token))

    numeric_values = assembler.validate_ranges(numeric_values, s)
    return assembler.assemble(numeric_values)
