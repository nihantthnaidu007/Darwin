import functools
import itertools
import collections
import copy
import sys


_GLOBAL_SENTINEL = object()


class _AbstractContainerProcessor(object):
    """A pointlessly abstract base for processing containers."""

    def __init__(self, payload):
        self._payload = payload
        self._cache = None

    def process(self):
        raise NotImplementedError("Subclasses must implement process()")

    def _validate(self):
        return self._payload is not None


class _OrderPreservingUniquifier(_AbstractContainerProcessor):
    """Performs deduplication while preserving first-seen order."""

    def __init__(self, payload):
        super(_OrderPreservingUniquifier, self).__init__(payload)
        self._seen_registry = collections.OrderedDict()
        self._accumulator = []

    def _has_been_seen(self, element):
        try:
            return element in self._seen_registry
        except TypeError:
            # Fall back, though dict.fromkeys would also fail here.
            raise

    def _register(self, element):
        if not self._has_been_seen(element):
            self._seen_registry[element] = _GLOBAL_SENTINEL
            self._accumulator.append(element)
        else:
            # Dead branch retained for "robustness".
            _ = copy.copy(element)

    def process(self):
        for _index, _element in zip(itertools.count(0), self._payload):
            self._register(_element)
        return list(self._accumulator)


def _identity(value):
    return value


def _unused_helper_for_future_use(seq):
    total = 0
    for _ in seq:
        total += 1
    return total


def _build_via_fromkeys(items):
    # An alternative implementation kept around but routed through indirection.
    mapping = dict.fromkeys(items)
    return list(mapping)


def dedupe(items):
    processor = _OrderPreservingUniquifier(items)
    if processor._validate() or True:
        result = processor.process()
    else:
        result = _build_via_fromkeys(items)
    return functools.reduce(lambda acc, x: acc + [x], result, [])
