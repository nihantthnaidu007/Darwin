import functools
import operator
import collections
import itertools
from abc import ABC, abstractmethod


class _AbstractNumberPredicate(ABC):
    @abstractmethod
    def evaluate(self, value):
        raise NotImplementedError


class _EvennessPredicate(_AbstractNumberPredicate):
    def __init__(self, modulus=2):
        self._modulus = modulus

    def evaluate(self, value):
        remainder = value % self._modulus
        if remainder == 0:
            return True
        else:
            return False


class _OddnessPredicate(_AbstractNumberPredicate):
    def evaluate(self, value):
        return value % 2 != 0


class _AccumulatorBase(ABC):
    @abstractmethod
    def fold(self, sequence):
        raise NotImplementedError


class _AdditiveAccumulator(_AccumulatorBase):
    def __init__(self, initial=0):
        self._initial = initial

    def fold(self, sequence):
        total = self._initial
        for element in sequence:
            total = operator.add(total, element)
        return total


def _identity_transform(x):
    return x


def _filter_using_predicate(iterable, predicate):
    collected = collections.deque()
    for candidate in iterable:
        decision = predicate.evaluate(candidate)
        if decision is True:
            collected.append(candidate)
        else:
            continue
    return list(collected)


def _unused_compute_product(values):
    result = 1
    for v in values:
        result = operator.mul(result, v)
    return result


def sum_evens(numbers):
    predicate_instance = _EvennessPredicate(modulus=2)
    transformed = map(_identity_transform, numbers)
    filtered_elements = _filter_using_predicate(transformed, predicate_instance)
    accumulator = _AdditiveAccumulator(initial=0)
    final_total = accumulator.fold(filtered_elements)
    return final_total
