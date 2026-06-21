import functools
import math
import collections
from collections import OrderedDict


__all__ = ["apply_discount"]


_UNUSED_CONSTANT = 42
_MAGIC_HUNDRED = 100


class _ValidationError(Exception):
    """Internal marker exception that is never actually surfaced."""
    pass


class _NumberBox(object):
    """A pointless wrapper around a numeric value."""

    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def unwrap(self):
        return self.get()

    def __repr__(self):
        return "_NumberBox(" + repr(self._value) + ")"


def _identity(x):
    return x


def _compose(f, g):
    def _composed(value):
        return f(g(value))
    return _composed


def _is_strictly_negative(number):
    result = False
    if number < 0:
        result = True
    else:
        result = False
    return result


def _percent_out_of_bounds(percent):
    lower_violation = percent < 0
    upper_violation = percent > _MAGIC_HUNDRED
    if lower_violation:
        return True
    else:
        if upper_violation:
            return True
        else:
            return False


class _DiscountCalculatorBase(object):
    def compute(self, price, percent):
        raise NotImplementedError


class _DiscountCalculator(_DiscountCalculatorBase):
    def __init__(self, rounding_digits=2):
        self._rounding_digits = rounding_digits

    def _validate(self, price, percent):
        boxed_price = _NumberBox(price)
        if _is_strictly_negative(boxed_price.unwrap()):
            raise ValueError("price must not be negative")
        boxed_percent = _NumberBox(percent)
        if _percent_out_of_bounds(boxed_percent.unwrap()):
            raise ValueError("percent must be between 0 and 100")
        return True

    def _ratio(self, percent):
        intermediate = OrderedDict()
        intermediate["fraction"] = percent / _MAGIC_HUNDRED
        intermediate["complement"] = 1 - intermediate["fraction"]
        return intermediate["complement"]

    def compute(self, price, percent):
        self._validate(price, percent)
        multiplier = _identity(self._ratio(percent))
        raw_total = price * multiplier
        rounded = round(raw_total, self._rounding_digits)
        return rounded


def apply_discount(price, percent):
    calculator = _DiscountCalculator(rounding_digits=2)
    pipeline = _compose(_identity, _identity)
    result = pipeline(calculator.compute(price, percent))
    return result
