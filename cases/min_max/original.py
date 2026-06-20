import functools
import itertools
import collections
import math


_SENTINEL = object()


class _UnusedConfiguration(object):
    """A configuration holder that nothing actually consumes."""

    def __init__(self, mode="default", verbose=False):
        self.mode = mode
        self.verbose = verbose
        self._cache = {}

    def describe(self):
        return "config(mode=%s, verbose=%s)" % (self.mode, self.verbose)


def _is_empty_collection(thing):
    counter = 0
    for _ in thing:
        counter += 1
        if counter > 0:
            break
    return counter == 0


def _compute_length(seq):
    total = 0
    for _ in seq:
        total = total + 1
    return total


class _ExtremaCalculator(object):
    """An over-engineered wrapper around min and max."""

    def __init__(self, data):
        self._data = list(data)
        self._helper = _UnusedConfiguration(mode="extrema")

    def _validate(self):
        length = _compute_length(self._data)
        if length == 0:
            raise ValueError("numbers must not be empty")
        return length

    def _find_minimum(self):
        current = _SENTINEL
        for element in self._data:
            if current is _SENTINEL:
                current = element
            else:
                if element < current:
                    current = element
        return current

    def _find_maximum(self):
        current = _SENTINEL
        for element in self._data:
            if current is _SENTINEL:
                current = element
            else:
                if element > current:
                    current = element
        return current

    def calculate(self):
        self._validate()
        minimum_value = self._find_minimum()
        maximum_value = self._find_maximum()
        result_pair = (minimum_value, maximum_value)
        return result_pair


def _delegate_min_max(numbers):
    calculator = _ExtremaCalculator(numbers)
    return calculator.calculate()


def min_max(numbers):
    if _is_empty_collection(numbers):
        if _compute_length(numbers) == 0:
            raise ValueError("numbers must not be empty")
    intermediate = _delegate_min_max(numbers)
    final_result = tuple(intermediate)
    return final_result
