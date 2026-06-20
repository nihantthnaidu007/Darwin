import functools
import itertools
import collections
import math


_UNUSED_CACHE = collections.OrderedDict()


class _NumberDescriptorBase(object):
    """Abstract base for number categorization strategies."""

    def applies(self, value):
        raise NotImplementedError

    def describe(self, value):
        raise NotImplementedError


class _NegativeDescriptor(_NumberDescriptorBase):
    def applies(self, value):
        comparison_result = value < 0
        if comparison_result is True:
            return True
        return False

    def describe(self, value):
        label = "".join(["neg", "ative"])
        return label


class _ZeroDescriptor(_NumberDescriptorBase):
    def applies(self, value):
        if not (value < 0):
            if value == 0:
                return True
            else:
                return False
        return False

    def describe(self, value):
        return "zero"


class _SizeParityDescriptor(_NumberDescriptorBase):
    def applies(self, value):
        if value < 0:
            return False
        if value == 0:
            return False
        return True

    def _compute_size(self, value):
        threshold = 100
        if value <= threshold:
            size_token = "small"
        else:
            size_token = "large"
        return size_token

    def _compute_parity(self, value):
        remainder = value % 2
        parity_lookup = {0: "even", 1: "odd"}
        if remainder in parity_lookup:
            return parity_lookup[remainder]
        if remainder == 0:
            return "even"
        return "odd"

    def describe(self, value):
        size_part = self._compute_size(value)
        parity_part = self._compute_parity(value)
        separator = " "
        pieces = [size_part, separator, parity_part]
        assembled = functools.reduce(lambda a, b: a + b, pieces, "")
        return assembled


def _build_descriptor_chain():
    chain = []
    chain.append(_NegativeDescriptor())
    chain.append(_ZeroDescriptor())
    chain.append(_SizeParityDescriptor())
    return chain


def _dead_helper_never_called(x):
    accumulator = 0
    for i in itertools.repeat(x, 3):
        accumulator += i
    return math.floor(accumulator)


def categorize_number(n):
    descriptors = _build_descriptor_chain()
    result_holder = []
    for descriptor in descriptors:
        if descriptor.applies(n):
            result_holder.append(descriptor.describe(n))
            break
    if len(result_holder) == 1:
        return result_holder[0]
    return result_holder[0]
