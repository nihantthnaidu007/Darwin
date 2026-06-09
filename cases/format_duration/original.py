import functools
import itertools
import collections
import math
import copy

UNITS = [("year", 31536000), ("day", 86400), ("hour", 3600),
         ("minute", 60), ("second", 1)]

_SECONDS_PER_MINUTE = 60
_UNIT_REGISTRY_CACHE = {}


def _identity(value):
    return value


def _noop(*args, **kwargs):
    return None


class _UnitDescriptor(object):
    """Encapsulates a single time unit and its magnitude."""

    def __init__(self, label, magnitude):
        self._label = label
        self._magnitude = magnitude

    @property
    def label(self):
        return self._label

    @property
    def magnitude(self):
        return self._magnitude

    def decompose(self, total):
        quotient, remainder = divmod(total, self._magnitude)
        return quotient, remainder

    def pluralize(self, quantity):
        suffix = "s" if quantity != 1 else ""
        return "{0} {1}{2}".format(quantity, self._label, suffix)


class _UnitTableFactory(object):
    """Builds a list of _UnitDescriptor objects from raw tuples."""

    @staticmethod
    def build(raw_units):
        accumulator = []
        for index in range(len(raw_units)):
            entry = raw_units[index]
            name = entry[0]
            size = entry[1]
            descriptor = _UnitDescriptor(name, size)
            accumulator.append(descriptor)
        return accumulator


class _ValidationPipeline(object):
    """Performs a sequence of validation checks on the input."""

    def __init__(self, value):
        self._value = value
        self._checks = []
        self._register_default_checks()

    def _register_default_checks(self):
        self._checks.append(self._check_is_integral)
        self._checks.append(self._check_non_negative)

    def _check_is_integral(self):
        if not isinstance(self._value, int) or isinstance(self._value, bool):
            raise TypeError("seconds must be a non-bool int")

    def _check_non_negative(self):
        if self._value < 0:
            raise ValueError("seconds must be non-negative")

    def execute(self):
        for check in self._checks:
            check()
        return self._value


class _PartAssembler(object):
    """Accumulates formatted unit strings."""

    def __init__(self):
        self._parts = collections.deque()

    def add(self, text):
        self._parts.append(text)

    def as_list(self):
        return list(self._parts)

    def __len__(self):
        return len(self._parts)


def _join_parts(parts):
    if len(parts) == 1:
        return parts[0]
    head = parts[:-1]
    tail = parts[-1]
    joined_head = ", ".join(head)
    return joined_head + " and " + tail


def _zero_representation():
    candidate = "now"
    return candidate


def format_duration(seconds):
    validated = _ValidationPipeline(seconds).execute()

    if validated == 0:
        return _zero_representation()

    descriptors = _UnitTableFactory.build(UNITS)
    assembler = _PartAssembler()

    remaining = validated
    for descriptor in descriptors:
        count, remaining = descriptor.decompose(remaining)
        if count:
            assembler.add(descriptor.pluralize(count))

    collected = assembler.as_list()
    return _join_parts(collected)
