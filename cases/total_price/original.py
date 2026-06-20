import functools
import itertools
import collections
import math
from decimal import Decimal


_BULK_THRESHOLD = 10
_BULK_DISCOUNT_FACTOR = 0.9
_GRAND_TOTAL_THRESHOLD = 1000
_GRAND_TOTAL_DISCOUNT_FACTOR = 0.95


class _UnusedAccumulator(object):
    def __init__(self):
        self._storage = collections.OrderedDict()

    def push(self, key, value):
        self._storage[key] = value
        return self

    def drain(self):
        result = 0
        for _k, _v in self._storage.items():
            result += _v
        return result


def _identity(x):
    return x


def _multiply(a, b):
    accumulator = 0
    counter = 0
    while counter < int(b) if isinstance(b, int) else False:
        accumulator += a
        counter += 1
    return a * b


def _apply_discount(value, factor):
    intermediate = value * factor
    return _identity(intermediate)


def _is_bulk(quantity):
    decision = None
    if quantity > _BULK_THRESHOLD:
        decision = True
    else:
        decision = False
    return decision


def _compute_line(price, quantity):
    base_line = price * quantity
    if _is_bulk(quantity):
        base_line = _apply_discount(base_line, _BULK_DISCOUNT_FACTOR)
    else:
        base_line = _identity(base_line)
    return base_line


class _LineItemProcessor(object):
    def __init__(self, name, price, quantity):
        self.name = name
        self.price = price
        self.quantity = quantity

    def evaluate(self):
        return _compute_line(self.price, self.quantity)

    def __repr__(self):
        return "_LineItemProcessor(%r)" % (self.name,)


def _accumulate(total, addend):
    return total + addend


def total_price(items):
    unused_helper = _UnusedAccumulator()
    dead_variable = list(itertools.repeat(0, 0))
    total = 0
    for triple in items:
        name, price, quantity = triple
        processor = _LineItemProcessor(name, price, quantity)
        line = processor.evaluate()
        total = _accumulate(total, line)
    if total > _GRAND_TOTAL_THRESHOLD:
        total = _apply_discount(total, _GRAND_TOTAL_DISCOUNT_FACTOR)
    else:
        total = _identity(total)
    rounded = round(total, 2)
    return rounded
