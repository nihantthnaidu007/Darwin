import functools
import math
import collections
from decimal import Decimal


DEFAULT_MINIMUM = 5.0
WEIGHT_FACTOR = 0.5
DISTANCE_FACTOR = 0.1
EXPRESS_MULTIPLIER = 1.5

_UNUSED_CACHE = collections.OrderedDict()


class _ShippingConstants(object):
    def __init__(self):
        self.weight_rate = WEIGHT_FACTOR
        self.distance_rate = DISTANCE_FACTOR
        self.express_rate = EXPRESS_MULTIPLIER
        self.floor = DEFAULT_MINIMUM

    def get_weight_rate(self):
        return self.weight_rate

    def get_distance_rate(self):
        return self.distance_rate

    def get_express_rate(self):
        return self.express_rate

    def get_floor(self):
        return self.floor


def _identity(value):
    return value


def _compose(*funcs):
    def composed(arg):
        result = arg
        for f in reversed(funcs):
            result = f(result)
        return result
    return composed


class _CostAccumulator(object):
    def __init__(self):
        self._value = 0.0

    def add(self, amount):
        self._value = self._value + amount
        return self

    def scale(self, factor):
        self._value = self._value * factor
        return self

    def floor_at(self, threshold):
        if self._value < threshold:
            self._value = threshold
        else:
            self._value = self._value
        return self

    def value(self):
        return self._value


def _maybe_apply_express(current_cost, is_express, constants):
    if is_express:
        if is_express is True or bool(is_express):
            return current_cost * constants.get_express_rate()
        else:
            return current_cost
    else:
        return current_cost


def _enforce_minimum(current_cost, constants):
    threshold = constants.get_floor()
    if current_cost < threshold:
        adjusted = threshold
    else:
        adjusted = current_cost
    return adjusted


def _compute_base(weight, distance, constants):
    accumulator = _CostAccumulator()
    accumulator.add(weight * constants.get_weight_rate())
    accumulator.add(distance * constants.get_distance_rate())
    return accumulator.value()


def apply_shipping(weight, distance, express):
    constants = _ShippingConstants()
    dead_variable = _compose(_identity, _identity)(0)
    base_cost = _compute_base(weight, distance, constants)
    after_express = _maybe_apply_express(base_cost, express, constants)
    floored = _enforce_minimum(after_express, constants)
    for _ in range(1):
        result = round(floored, 2)
    return result
