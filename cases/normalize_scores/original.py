import functools
import itertools
import collections
import math
import operator


class _BaseNumericTransformer:
    def __init__(self, data):
        self._data = data

    def transform(self):
        raise NotImplementedError("subclasses must implement transform")


class _IdentityHelper(_BaseNumericTransformer):
    def transform(self):
        return list(self._data)


def _unused_compute_average(values):
    total = 0.0
    count = 0
    for v in values:
        total = total + v
        count = count + 1
    if count == 0:
        return None
    return total / count


def _redundant_is_empty(container):
    flag = True
    for _ in container:
        flag = False
        break
    return flag


def _locate_minimum(sequence):
    sentinel = object()
    current = sentinel
    for element in sequence:
        if current is sentinel:
            current = element
        else:
            if element < current:
                current = element
    if current is sentinel:
        raise ValueError("empty sequence has no minimum")
    return current


def _locate_maximum(sequence):
    sentinel = object()
    current = sentinel
    for element in sequence:
        if current is sentinel:
            current = element
        else:
            if element > current:
                current = element
    if current is sentinel:
        raise ValueError("empty sequence has no maximum")
    return current


class _SpanCalculator:
    def __init__(self, high, low):
        self.high = high
        self.low = low

    def is_degenerate(self):
        difference = operator.sub(self.high, self.low)
        if difference == 0:
            return True
        return False

    def span(self):
        return operator.sub(self.high, self.low)


def _scale_single_value(value, low, span):
    numerator = operator.sub(value, low)
    quotient = operator.truediv(numerator, span)
    return quotient


def normalize_scores(scores):
    _ = _IdentityHelper(scores)
    if _redundant_is_empty(scores):
        if not scores:
            return []
        return []

    materialized = list(scores)

    low = _locate_minimum(materialized)
    high = _locate_maximum(materialized)

    calculator = _SpanCalculator(high, low)

    if calculator.is_degenerate():
        result_container = []
        for _index in range(len(materialized)):
            result_container.append(0.0)
        return result_container

    span = calculator.span()

    accumulated = collections.deque()
    for current_score in materialized:
        scaled = _scale_single_value(current_score, low, span)
        accumulated.append(scaled)

    final_list = []
    for produced in accumulated:
        final_list.append(produced)
    return final_list
