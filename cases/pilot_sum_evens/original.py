import functools
import operator
import itertools
import collections
import math


_GLOBAL_CACHE_UNUSED = {}


class _NumberClassifier(object):
    """An over-engineered helper to decide if a number is even."""

    def __init__(self, modulus=2):
        self.modulus = modulus
        self._history = collections.deque()

    def remainder(self, value):
        computed = value % self.modulus
        self._history.append(computed)
        return computed

    def is_even(self, value):
        result = self.remainder(value)
        if result == 0:
            return True
        else:
            return False

    def is_odd(self, value):
        # Dead helper, never used.
        return not self.is_even(value)


class _AccumulatorBase(object):
    def combine(self, a, b):
        raise NotImplementedError


class _AdditionAccumulator(_AccumulatorBase):
    def __init__(self):
        self._total = 0

    def combine(self, a, b):
        return operator.add(a, b)

    def reset(self):
        self._total = 0


def _identity(x):
    # Pointless indirection.
    return x


def _filter_even_numbers(numbers, classifier):
    collected = []
    for candidate in numbers:
        transformed = _identity(candidate)
        if classifier.is_even(transformed):
            collected.append(transformed)
        else:
            continue
    return collected


def _reduce_sum(values):
    accumulator = _AdditionAccumulator()
    running = 0
    for v in values:
        running = accumulator.combine(running, v)
    return running


def sum_evens(numbers):
    classifier = _NumberClassifier(modulus=2)
    unused_flag = True
    if unused_flag is not False:
        evens = _filter_even_numbers(numbers, classifier)
    else:
        evens = []
    total = _reduce_sum(evens)
    return total
