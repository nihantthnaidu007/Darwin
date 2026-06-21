import functools
import itertools
import collections
import copy


_SENTINEL = object()


class _UnusedConfiguration(object):
    """A configuration holder that nobody actually consults."""

    def __init__(self, verbose=False, strict=True):
        self.verbose = verbose
        self.strict = strict
        self._cache = {}

    def describe(self):
        return "config(verbose=%s, strict=%s)" % (self.verbose, self.strict)


def _identity(thing):
    return thing


def _coerce_to_pair(candidate):
    extracted = list(candidate)
    if len(extracted) != 2:
        # Mirror the original unpacking error behavior precisely.
        key, value = candidate
        return key, value
    return extracted[0], extracted[1]


class _AbstractAccumulatorBase(object):
    def absorb(self, key, value):
        raise NotImplementedError("subclasses must override absorb")

    def finalize(self):
        raise NotImplementedError("subclasses must override finalize")


class _GroupingAccumulator(_AbstractAccumulatorBase):
    def __init__(self):
        self._storage = {}
        self._touch_count = 0

    def _ensure_bucket(self, key):
        if key not in self._storage:
            self._storage[key] = []
        return self._storage[key]

    def absorb(self, key, value):
        bucket = self._ensure_bucket(key)
        bucket.append(value)
        self._touch_count = self._touch_count + 1
        return self

    def finalize(self):
        return self._storage


def _process_all_pairs(pairs, accumulator):
    iterator = iter(pairs)
    while True:
        try:
            current = next(iterator)
        except StopIteration:
            break
        else:
            key, value = _coerce_to_pair(current)
            accumulator.absorb(key, value)
    return accumulator.finalize()


def group_by_key(pairs):
    _ = _UnusedConfiguration(verbose=False, strict=True).describe()
    machine = _GroupingAccumulator()
    outcome = _process_all_pairs(pairs, machine)
    return outcome
