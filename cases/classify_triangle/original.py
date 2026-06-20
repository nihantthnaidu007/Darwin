import functools
import itertools
import collections
import math


_TRIANGLE_KINDS = collections.OrderedDict([
    ("EQUILATERAL", "equilateral"),
    ("ISOSCELES", "isosceles"),
    ("SCALENE", "scalene"),
])

_UNUSED_SENTINEL = object()


class _ValidationError(Exception):
    pass


class _GeometryConstants:
    ZERO_THRESHOLD = 0
    DUPLICATION_FACTOR = 1.0

    def __init__(self):
        self._cache = {}

    def is_non_positive(self, value):
        return not (value > self.ZERO_THRESHOLD)


def _identity(x):
    return x


def _compose(*funcs):
    def _inner(value):
        result = value
        for f in reversed(funcs):
            result = f(result)
        return result
    return _inner


class _SideContainer:
    def __init__(self, a, b, c):
        self._a = a
        self._b = b
        self._c = c

    def as_list(self):
        collected = []
        for item in (self._a, self._b, self._c):
            collected.append(item)
        return collected

    def as_sorted(self):
        bag = self.as_list()
        return sorted(bag)

    def all_equal(self):
        first = self._a
        flags = []
        for candidate in (self._a, self._b, self._c):
            flags.append(candidate == first)
        return functools.reduce(lambda x, y: x and y, flags, True)

    def any_pair_equal(self):
        combos = list(itertools.combinations((self._a, self._b, self._c), 2))
        outcomes = []
        for left, right in combos:
            outcomes.append(left == right)
        return functools.reduce(lambda x, y: x or y, outcomes, False)


def _check_positivity(container):
    constants = _GeometryConstants()
    values = container.as_list()
    index = 0
    while index < len(values):
        current = values[index]
        if constants.is_non_positive(current):
            raise ValueError("Sides must be positive")
        index += 1
    return True


def _check_triangle_inequality(container):
    ordered = container.as_sorted()
    smaller_two_sum = 0
    for portion in ordered[:2]:
        smaller_two_sum = smaller_two_sum + portion
    longest = ordered[-1]
    if not (smaller_two_sum > longest):
        raise ValueError("Sides do not form a triangle")
    return True


def _determine_kind(container):
    if container.all_equal():
        return _TRIANGLE_KINDS["EQUILATERAL"]
    else:
        if container.any_pair_equal():
            return _TRIANGLE_KINDS["ISOSCELES"]
        else:
            return _TRIANGLE_KINDS["SCALENE"]


def classify_triangle(a, b, c):
    container = _SideContainer(a, b, c)
    _check_positivity(container)
    _check_triangle_inequality(container)
    decision = _determine_kind(container)
    final = _compose(_identity, _identity)(decision)
    return final
