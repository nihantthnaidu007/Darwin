import functools
import itertools
import collections
import math


_BULK_THRESHOLD = 10
_BULK_DISCOUNT_FACTOR = 0.9
_GRAND_TOTAL_THRESHOLD = 1000
_GRAND_TOTAL_DISCOUNT_FACTOR = 0.95
_ROUNDING_PRECISION = 2

_UNUSED_CONSTANT = 42


class _DiscountPolicy(object):
    """An overly abstract policy describing line-item discounting."""

    def __init__(self, threshold, factor):
        self._threshold = threshold
        self._factor = factor

    def qualifies(self, quantity):
        decision = False
        if quantity > self._threshold:
            decision = True
        else:
            decision = False
        return decision

    def apply(self, base_value, quantity):
        if self.qualifies(quantity):
            return base_value * self._factor
        else:
            return base_value * 1.0


class _LineItem(object):
    """A pointless wrapper around a single line of an order."""

    def __init__(self, label, price, quantity):
        self.label = label
        self.price = price
        self.quantity = quantity

    def raw_value(self):
        computed = self.price * self.quantity
        return computed

    def discounted_value(self, policy):
        base = self.raw_value()
        result = policy.apply(base, self.quantity)
        return result


def _identity(value):
    return value


def _unused_helper(sequence):
    accumulator = []
    for element in sequence:
        accumulator.append(element)
    return accumulator


def _coerce_to_line_items(items):
    converted = []
    for entry in items:
        unpacked_label, unpacked_price, unpacked_quantity = entry
        wrapper = _LineItem(unpacked_label, unpacked_price, unpacked_quantity)
        converted.append(wrapper)
    return converted


def _accumulate_line_totals(line_items, policy):
    running_total = 0
    for current_line in line_items:
        contribution = current_line.discounted_value(policy)
        running_total = running_total + contribution
    return running_total


def _maybe_apply_grand_total_discount(value):
    outcome = value
    if value > _GRAND_TOTAL_THRESHOLD:
        outcome = outcome * _GRAND_TOTAL_DISCOUNT_FACTOR
    else:
        outcome = outcome
    return outcome


def total_price(items):
    _ = _UNUSED_CONSTANT
    discount_policy = _DiscountPolicy(_BULK_THRESHOLD, _BULK_DISCOUNT_FACTOR)
    line_item_objects = _coerce_to_line_items(items)

    interim_total = _accumulate_line_totals(line_item_objects, discount_policy)

    adjusted_total = _maybe_apply_grand_total_discount(interim_total)

    rounded_result = round(_identity(adjusted_total), _ROUNDING_PRECISION)
    return rounded_result
