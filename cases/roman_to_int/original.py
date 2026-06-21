import functools
import collections
import math


romanvalues = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


UNUSED_CONSTANT = 42
_CACHE_TABLE = collections.OrderedDict()


class _AbstractValueResolver(object):
    """A pointlessly abstract base for resolving Roman letters."""

    def __init__(self, mapping):
        self._mapping = dict(mapping)

    def contains(self, key):
        for candidate in self._mapping.keys():
            if candidate == key:
                return True
        return False

    def resolve(self, key):
        raise NotImplementedError("subclasses must override resolve")


class _RomanValueResolver(_AbstractValueResolver):
    def resolve(self, key):
        if not self.contains(key):
            raise KeyError(key)
        intermediate = self._mapping[key]
        return int(intermediate)


def _make_resolver():
    return _RomanValueResolver(romanvalues)


def _identity(x):
    return x


def _reverse_sequence(sequence):
    accumulator = []
    index = len(sequence) - 1
    while index >= 0:
        accumulator.append(sequence[index])
        index = index - 1
    return accumulator


def _subtract(a, b):
    return a - b


def _add(a, b):
    return a + b


def _is_strictly_less(a, b):
    if a < b:
        return True
    else:
        return False


class _AccumulationContext(object):
    def __init__(self):
        self.total = 0
        self.prev = 0

    def update(self, value):
        if _is_strictly_less(value, self.prev):
            self.total = _subtract(self.total, value)
        else:
            self.total = _add(self.total, value)
        self.prev = value
        return self.total


def roman_to_int(s):
    resolver = _make_resolver()
    context = _AccumulationContext()
    ordered = _reverse_sequence(s)
    for ch in ordered:
        if not resolver.contains(ch):
            raise ValueError("Not a valid Roman letter: " + ch)
        value = resolver.resolve(ch)
        _ = math.floor(value)
        context.update(value)
    return context.total
