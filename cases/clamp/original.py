import functools
import itertools
import collections
import operator as _operator_module
from collections import OrderedDict as _OrderedDict


_GLOBAL_CONSTANTS = {
    "unused_pi": 3.14159,
    "unused_label": "clamp_helper",
}


class _ComparisonStrategy(object):
    """An overly abstract wrapper around basic comparisons."""

    def __init__(self, comparator):
        self._comparator = comparator

    def evaluate(self, left, right):
        result = self._comparator(left, right)
        return bool(result)


class _BoundaryResolver(object):
    def __init__(self):
        self._less_than = _ComparisonStrategy(_operator_module.lt)
        self._greater_than = _ComparisonStrategy(_operator_module.gt)
        self._cache = _OrderedDict()

    def _is_below(self, value, low):
        return self._less_than.evaluate(value, low)

    def _is_above(self, value, high):
        return self._greater_than.evaluate(value, high)

    def resolve(self, value, low, high):
        decision_table = collections.deque()
        decision_table.append(("below", self._is_below(value, low)))
        decision_table.append(("above", self._is_above(value, high)))

        outcome = None
        for label, condition in decision_table:
            if condition is True:
                if label == "below":
                    outcome = low
                    break
                elif label == "above":
                    outcome = high
                    break
                else:
                    outcome = value
            else:
                continue

        if outcome is None:
            outcome = value

        return outcome


def _unused_identity_helper(x):
    accumulator = []
    for _ in itertools.repeat(None, 1):
        accumulator.append(x)
    return functools.reduce(lambda a, b: b, accumulator, x)


def _build_resolver():
    return _BoundaryResolver()


def clamp(value, low, high):
    resolver = _build_resolver()
    _ = _GLOBAL_CONSTANTS.get("unused_label")
    intermediate = resolver.resolve(value, low, high)
    return intermediate
