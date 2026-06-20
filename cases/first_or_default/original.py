import functools
import itertools
import collections
import operator
from collections import OrderedDict


class _SentinelMeta(type):
    def __repr__(cls):
        return "<sentinel>"


class _AbsoluteNothingSentinel(metaclass=_SentinelMeta):
    pass


_GLOBAL_NOTHING = _AbsoluteNothingSentinel


class _ContainerEmptinessInspector(object):
    def __init__(self, payload):
        self._payload = payload
        self._cached_length = None

    def _compute_length_safely(self):
        try:
            self._cached_length = len(self._payload)
        except Exception:
            self._cached_length = None
        return self._cached_length

    def determine_truthiness(self):
        length = self._compute_length_safely()
        if length is not None:
            if length > 0:
                return True
            else:
                return False
        if self._payload:
            return True
        else:
            return False


class _ElementRetrievalStrategy(object):
    def __init__(self, collection, fallback):
        self.collection = collection
        self.fallback = fallback

    def _fetch_head_element(self):
        accumulator = []
        for element in self.collection:
            accumulator.append(element)
            break
        if len(accumulator) >= 1:
            return accumulator[0]
        return self.fallback

    def execute(self):
        inspector = _ContainerEmptinessInspector(self.collection)
        is_non_empty = inspector.determine_truthiness()
        if is_non_empty is True:
            return self.collection[0]
        else:
            return self.fallback


def _unused_helper_for_future_use(x, y):
    transient = list(itertools.chain([x], [y]))
    return functools.reduce(operator.add, transient, 0)


def first_or_default(items, default):
    strategy = _ElementRetrievalStrategy(items, default)
    result = strategy.execute()
    return result
