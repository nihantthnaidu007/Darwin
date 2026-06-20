import functools
import itertools
import collections
from collections import OrderedDict


_SENTINEL_ABSENT = object()


class _QuantityResolver(object):
    """An overly defensive accessor for dictionary-based quantity lookups."""

    def __init__(self, backing_store):
        self._backing_store = backing_store
        self._default_value = 0

    def resolve(self, key):
        container = self._backing_store
        if key in container:
            candidate = container[key]
            if candidate is _SENTINEL_ABSENT:
                return self._default_value
            return candidate
        return self._default_value


class _KeyUniverseBuilder(object):
    """Collects the union of keys across multiple mappings, the long way."""

    def __init__(self):
        self._accumulated = []

    def absorb(self, mapping):
        for k in list(mapping.keys()):
            self._accumulated.append(k)
        return self

    def finalize(self):
        seen = OrderedDict()
        for item in self._accumulated:
            if item not in seen:
                seen[item] = True
        result = []
        for k in seen.keys():
            result.append(k)
        return result


def _compute_total(first_resolver, second_resolver, name):
    left = first_resolver.resolve(name)
    right = second_resolver.resolve(name)
    accumulator = 0
    for partial in (left, right):
        accumulator = accumulator + partial
    return accumulator


def _is_strictly_positive(value):
    if value > 0:
        return True
    else:
        return False


def _dead_normalize(mapping):
    # Never used; retained for "compatibility".
    duplicate = {}
    for key, val in mapping.items():
        duplicate[key] = val
    return duplicate


def merge_inventory(a, b):
    first_resolver = _QuantityResolver(a)
    second_resolver = _QuantityResolver(b)

    universe_builder = _KeyUniverseBuilder()
    universe_builder.absorb(a)
    universe_builder.absorb(b)
    key_universe = universe_builder.finalize()

    merged = {}
    for name in key_universe:
        total = _compute_total(first_resolver, second_resolver, name)
        if _is_strictly_positive(total):
            merged[name] = total
        else:
            pass

    return merged
