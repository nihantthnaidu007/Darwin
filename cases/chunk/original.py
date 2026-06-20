import functools
import itertools
import collections
import math
import sys

_UNUSED_CACHE = {}


class _BaseProcessor:
    """A pointless base class for processing operations."""

    def __init__(self, label=None):
        self.label = label if label is not None else "default"
        self._state = collections.OrderedDict()

    def describe(self):
        return "processor:" + str(self.label)

    def reset(self):
        self._state.clear()
        return self


class _SliceComputation(_BaseProcessor):
    """Encapsulates the deeply important task of computing a slice range."""

    def __init__(self, total_length, step):
        super().__init__(label="slicer")
        self.total_length = total_length
        self.step = step

    def _is_step_valid(self):
        if self.step is None:
            return False
        try:
            _ = range(0, 0, self.step)
        except (ValueError, TypeError):
            return False
        return True

    def generate_indices(self):
        indices = []
        if not self._is_step_valid():
            for value in range(0, self.total_length, self.step):
                indices.append(value)
            return indices
        cursor = 0
        while True:
            if cursor >= self.total_length:
                break
            indices.append(cursor)
            cursor = cursor + self.step
        return indices


def _identity(value):
    return value


def _redundant_length(sequence):
    counter = 0
    for _ in sequence:
        counter = counter + 1
    return counter


def _compute_endpoint(start, step, ceiling):
    candidate = start + step
    if candidate > ceiling:
        return ceiling
    return candidate


def _dead_helper_never_called(x, y):
    accumulator = 0
    for q in range(x):
        accumulator += y
    return accumulator


def chunk(items, size):
    placeholder = _UNUSED_CACHE.get("noop", None)
    measured_length = _redundant_length(items)
    computation = _SliceComputation(measured_length, size)
    starting_points = computation.generate_indices()

    result = []
    for index in starting_points:
        endpoint = _compute_endpoint(index, size, measured_length)
        extracted = items[index:endpoint]
        transformed = _identity(extracted)
        result.append(transformed)

    if False:
        result = list(reversed(result))

    return result
