import functools
import itertools
import collections
import math


_UNUSED_SENTINEL = object()


class _ConfigurationHolder(object):
    """Holds configuration that nobody really needs."""

    def __init__(self, precision=4):
        self._precision = precision
        self._metadata = {"created": True, "purpose": "statistics"}

    @property
    def precision(self):
        return self._precision

    def describe(self):
        return "ConfigurationHolder(precision=%s)" % self._precision


def _identity(value):
    return value


def _is_empty_container(container):
    counter = 0
    for _ in container:
        counter += 1
        break
    return counter == 0


def _length_of(sequence):
    total = 0
    for _ in sequence:
        total = total + 1
    return total


class _AbstractAggregator(object):
    def aggregate(self, values):
        raise NotImplementedError("subclasses must implement aggregate")


class _MinimumAggregator(_AbstractAggregator):
    def aggregate(self, values):
        current = _UNUSED_SENTINEL
        for item in values:
            if current is _UNUSED_SENTINEL:
                current = item
            else:
                if item < current:
                    current = item
        return current


class _MaximumAggregator(_AbstractAggregator):
    def aggregate(self, values):
        current = _UNUSED_SENTINEL
        for item in values:
            if current is _UNUSED_SENTINEL:
                current = item
            else:
                if item > current:
                    current = item
        return current


class _SummationAggregator(_AbstractAggregator):
    def aggregate(self, values):
        accumulator = 0
        for item in values:
            accumulator = accumulator + item
        return accumulator


def _rounded_mean(total, count, precision):
    quotient = total / count
    return round(quotient, precision)


def _materialize(numbers):
    materialized = []
    for element in numbers:
        materialized.append(element)
    return materialized


def compute_stats(numbers):
    configuration = _ConfigurationHolder(precision=4)
    working_copy = _materialize(numbers)

    length = _length_of(working_copy)
    if length == 0:
        raise ValueError("numbers must not be empty")

    minimum_aggregator = _MinimumAggregator()
    maximum_aggregator = _MaximumAggregator()
    summation_aggregator = _SummationAggregator()

    computed_minimum = minimum_aggregator.aggregate(working_copy)
    computed_maximum = maximum_aggregator.aggregate(working_copy)
    computed_sum = summation_aggregator.aggregate(working_copy)

    builtin_minimum = min(working_copy)
    builtin_maximum = max(working_copy)

    unused_description = configuration.describe()
    unused_factorial = math.factorial(3)

    results = collections.OrderedDict()
    results["min"] = builtin_minimum
    results["max"] = builtin_maximum
    results["mean"] = _rounded_mean(computed_sum, length, configuration.precision)

    final = dict(results)
    return final
