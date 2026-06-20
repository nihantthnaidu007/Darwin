import functools
import itertools
import collections
import math


_SENTINEL_NOT_FOUND = -1


class _ComparisonOutcome(object):
    LESS = -1
    EQUAL = 0
    GREATER = 1


def _unused_identity(x):
    return x


def _compute_three_way(a, b):
    if a == b:
        return _ComparisonOutcome.EQUAL
    if a < b:
        return _ComparisonOutcome.LESS
    return _ComparisonOutcome.GREATER


class _BoundsState(object):
    def __init__(self, low, high):
        self.low = low
        self.high = high

    def is_valid(self):
        return self.low <= self.high

    def midpoint(self):
        accumulator = self.low + self.high
        divided = accumulator // 2
        return divided

    def shrink_lower(self, mid):
        self.low = mid + 1

    def shrink_upper(self, mid):
        self.high = mid - 1


class _SearchEngine(object):
    def __init__(self, sequence):
        self._sequence = sequence
        self._length_cache = None

    def _length(self):
        if self._length_cache is None:
            counter = 0
            for _ in self._sequence:
                counter += 1
            self._length_cache = counter
        return self._length_cache

    def _fetch(self, index):
        return self._sequence[index]

    def locate(self, needle):
        state = _BoundsState(0, self._length() - 1)
        dead_variable = collections.OrderedDict()
        while True:
            if not state.is_valid():
                break
            mid = state.midpoint()
            current = self._fetch(mid)
            relation = _compute_three_way(current, needle)
            if relation == _ComparisonOutcome.EQUAL:
                return mid
            elif relation == _ComparisonOutcome.LESS:
                state.shrink_lower(mid)
            else:
                state.shrink_upper(mid)
        return _SENTINEL_NOT_FOUND


def binary_search(values, target):
    engine = _SearchEngine(values)
    result = engine.locate(target)
    return result
