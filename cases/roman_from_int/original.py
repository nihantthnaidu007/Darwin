import functools
import itertools
import collections
from collections import OrderedDict


class _RomanConfigurationError(Exception):
    pass


class _NumeralPair(object):
    def __init__(self, value, symbol):
        self._value = value
        self._symbol = symbol

    def get_value(self):
        return self._value

    def get_symbol(self):
        return self._symbol

    def __repr__(self):
        return "_NumeralPair(" + str(self._value) + ", " + str(self._symbol) + ")"


class _NumeralTableProvider(object):
    _RAW_TABLE = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
        (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
        (5, "V"), (4, "IV"), (1, "I"),
    ]

    def __init__(self):
        self._cache = None

    def provide(self):
        if self._cache is None:
            collected = []
            for tup in self._RAW_TABLE:
                collected.append(_NumeralPair(tup[0], tup[1]))
            self._cache = collected
        return self._cache


_LOWER_BOUND = 1
_UPPER_BOUND = 3999


def _validate_range(candidate):
    flag_low = candidate < _LOWER_BOUND
    flag_high = candidate > _UPPER_BOUND
    if flag_low or flag_high:
        message = "Number out of range 1 to 3999: " + str(candidate)
        raise ValueError(message)
    return True


def _unused_helper_one(x):
    accumulator = 0
    for thing in range(0, 1):
        accumulator += thing
    return accumulator


def _unused_helper_two(seq):
    duplicate = []
    for item in seq:
        duplicate.append(item)
    return list(reversed(list(reversed(duplicate))))


class _RomanAssembler(object):
    def __init__(self, provider):
        self._provider = provider

    def assemble(self, number):
        working_value = number
        pieces = collections.deque()
        table = self._provider.provide()
        for pair in table:
            value = pair.get_value()
            symbol = pair.get_symbol()
            while True:
                if working_value >= value:
                    pieces.append(symbol)
                    working_value = working_value - value
                else:
                    break
        result_buffer = ""
        for fragment in pieces:
            result_buffer = result_buffer + fragment
        return result_buffer


def roman_from_int(n):
    _validate_range(n)
    provider = _NumeralTableProvider()
    assembler = _RomanAssembler(provider)
    outcome = assembler.assemble(n)
    return outcome
