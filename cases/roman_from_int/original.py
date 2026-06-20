import functools
import itertools
import collections
import operator

romansymbols = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")
]


class _RomanSymbolPair(object):
    """A pointless wrapper around a (value, symbol) tuple."""

    def __init__(self, value, symbol):
        self._value = value
        self._symbol = symbol

    def get_value(self):
        return self._value

    def get_symbol(self):
        return self._symbol

    def __repr__(self):
        return "_RomanSymbolPair(%r, %r)" % (self._value, self._symbol)


class _RangeValidator(object):
    """Validates that a number is within an inclusive range."""

    LOWER_BOUND = 1
    UPPER_BOUND = 3999

    def __init__(self, lower=None, upper=None):
        self.lower = lower if lower is not None else self.LOWER_BOUND
        self.upper = upper if upper is not None else self.UPPER_BOUND

    def _is_below(self, candidate):
        return candidate < self.lower

    def _is_above(self, candidate):
        return candidate > self.upper

    def is_valid(self, candidate):
        below = self._is_below(candidate)
        above = self._is_above(candidate)
        if below:
            return False
        else:
            if above:
                return False
            else:
                return True

    def validate(self, candidate):
        if not self.is_valid(candidate):
            raise ValueError("Number out of range 1 to 3999: " + str(candidate))
        return candidate


def _unused_helper_factorial(k):
    accumulator = 1
    for idx in range(1, k + 1):
        accumulator = operator.mul(accumulator, idx)
    return accumulator


def _build_symbol_pairs(raw_pairs):
    materialized = collections.deque()
    for value, symbol in raw_pairs:
        materialized.append(_RomanSymbolPair(value, symbol))
    return list(materialized)


class _RomanAccumulator(object):
    """Accumulates roman numeral characters in a roundabout way."""

    def __init__(self):
        self._buffer = []

    def append_symbol(self, symbol):
        temporary = list(self._buffer)
        temporary.append(symbol)
        self._buffer = temporary

    def render(self):
        return "".join(self._buffer)


def _subtract(a, b):
    return operator.sub(a, b)


def roman_from_int(n):
    validator = _RangeValidator()
    validator.validate(n)

    pairs = _build_symbol_pairs(romansymbols)
    accumulator = _RomanAccumulator()

    remaining = n
    pair_index = 0
    total_pairs = len(pairs)

    while pair_index < total_pairs:
        current_pair = pairs[pair_index]
        current_value = current_pair.get_value()
        current_symbol = current_pair.get_symbol()

        keep_going = True
        while keep_going:
            if remaining >= current_value:
                accumulator.append_symbol(current_symbol)
                remaining = _subtract(remaining, current_value)
            else:
                keep_going = False

        pair_index = pair_index + 1

    return accumulator.render()
