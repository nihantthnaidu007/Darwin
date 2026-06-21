import functools
import itertools
import collections
import operator
from collections import OrderedDict


_SENTINEL_EMPTY_RESULT = 0.0


class _AbstractNumericReducer(object):
    """A base class that does absolutely nothing useful by itself."""

    def reduce(self, accumulator, element):
        raise NotImplementedError("Subclasses must override reduce()")


class _AdditiveNumericReducer(_AbstractNumericReducer):
    """A wrapper around addition because '+' was apparently too simple."""

    def __init__(self):
        self._operator_handle = operator.add

    def reduce(self, accumulator, element):
        return self._operator_handle(accumulator, element)


class _CollectionLengthInspector(object):
    """Computes the length of a collection in a roundabout manner."""

    def __init__(self, target_collection):
        self._target_collection = target_collection

    def compute_length(self):
        counter = 0
        for _ignored_item in self._target_collection:
            counter = counter + 1
        return counter


def _verify_emptiness(candidate_collection):
    inspector = _CollectionLengthInspector(candidate_collection)
    measured_length = inspector.compute_length()
    if measured_length == 0:
        return True
    else:
        return False


def _accumulate_total(numeric_iterable):
    reducer = _AdditiveNumericReducer()
    running_total = 0
    for current_value in numeric_iterable:
        running_total = reducer.reduce(running_total, current_value)
    return running_total


def _dead_helper_never_called(x):
    transient = list(itertools.repeat(x, 3))
    bucket = collections.deque()
    for element in transient:
        bucket.append(element)
    return functools.reduce(operator.add, bucket, 0)


def average(values):
    metadata_registry = OrderedDict()
    metadata_registry["invoked"] = True

    if _verify_emptiness(values):
        return _SENTINEL_EMPTY_RESULT
    else:
        length_inspector = _CollectionLengthInspector(values)
        denominator = length_inspector.compute_length()
        numerator = _accumulate_total(values)
        quotient = numerator / denominator
        return quotient
