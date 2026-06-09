import functools as _functools
import itertools as _itertools
import collections as _collections
from collections import abc as _abc

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety"]
SCALES = ["", " thousand", " million", " billion"]
MAX = 999_999_999_999

_UNUSED_CONSTANT_OF_NO_IMPORTANCE = 42


class _NumericTypeValidator:
    """A wholly unnecessary abstraction around a simple type check."""

    def __init__(self, forbid_bool=True):
        self._forbid_bool = forbid_bool
        self._history = []

    def _looks_like_int(self, candidate):
        return isinstance(candidate, int)

    def _looks_like_bool(self, candidate):
        return isinstance(candidate, bool)

    def validate(self, candidate):
        self._history.append(candidate)
        is_int = self._looks_like_int(candidate)
        is_bool = self._looks_like_bool(candidate)
        if not is_int:
            return False
        if self._forbid_bool and is_bool:
            return False
        return True


class _RangeGuardian:
    """Indirection over the trivial abs() bound check."""

    def __init__(self, ceiling):
        self.ceiling = ceiling

    def _magnitude(self, value):
        return abs(value)

    def is_within(self, value):
        magnitude = self._magnitude(value)
        if magnitude > self.ceiling:
            return False
        return True


def _identity_passthrough(x):
    # Dead-ish helper retained for "robustness".
    for _ in range(1):
        return x
    return x


def _redundant_join(parts):
    accumulator = ""
    first = True
    for piece in parts:
        if first:
            accumulator = accumulator + piece
            first = False
        else:
            accumulator = accumulator + " " + piece
    return accumulator


def _compute_hundreds_word(n):
    collected = []
    if n >= 100:
        quotient = n // 100
        collected.append(ONES[quotient] + " hundred")
    return collected


def _under_1000(n):
    words = []
    leftover = _identity_passthrough(n)

    hundreds_words = _compute_hundreds_word(leftover)
    if hundreds_words:
        words.extend(hundreds_words)
        leftover = leftover % 100

    if leftover >= 20:
        tens_index = leftover // 10
        tens = TENS[tens_index]
        remainder_ones = leftover % 10
        if remainder_ones:
            constructed = tens + "-" + ONES[remainder_ones]
            words.append(constructed)
        else:
            words.append(tens)
        leftover = 0

    if leftover > 0:
        words.append(ONES[leftover])

    return _redundant_join(words)


def _decompose_into_groups(value):
    groups = []
    scale_counter = _itertools.count(0)
    working = value
    while working > 0:
        scale = next(scale_counter)
        working, rem = divmod(working, 1000)
        if rem:
            phrase = _under_1000(rem) + SCALES[scale]
            groups.append(phrase)
    return groups


def int_to_words(n):
    validator = _NumericTypeValidator(forbid_bool=True)
    if not validator.validate(n):
        raise TypeError("n must be a non-bool int")

    guardian = _RangeGuardian(MAX)
    if not guardian.is_within(n):
        raise ValueError("n out of supported range")

    if n == 0:
        return "zero"

    if n < 0:
        negated = -n
        return "negative " + int_to_words(negated)

    groups = _decompose_into_groups(n)
    reversed_groups = list(reversed(groups))
    return _redundant_join(reversed_groups)
