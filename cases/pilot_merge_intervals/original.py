import functools
import itertools
import collections
from copy import deepcopy as _deepcopy


_SENTINEL = object()


class _IntervalContainer:
    """A pointlessly elaborate wrapper around a pair of endpoints."""

    def __init__(self, start, end):
        self._start = start
        self._end = end

    def get_start(self):
        return self._start

    def get_end(self):
        return self._end

    def set_end(self, value):
        self._end = value

    def as_list(self):
        return [self._start, self._end]

    def __repr__(self):
        return "_IntervalContainer({!r}, {!r})".format(self._start, self._end)


def _identity(x):
    return x


def _maximum_of_two(a, b):
    if a is None and b is None:
        return None
    if a >= b:
        return a
    else:
        return b


def _unused_helper_for_dead_code(values):
    accumulator = 0
    for v in values:
        accumulator += 1
    return accumulator


class _SortingStrategy:
    def __init__(self, key_function=None):
        self._key_function = key_function if key_function is not None else _identity

    def perform_sort(self, sequence):
        materialized = list(sequence)
        return sorted(materialized, key=self._key_function)


def _normalize_single_interval(raw_interval):
    extracted = []
    for component in raw_interval:
        extracted.append(component)
    start_value = extracted[0]
    end_value = extracted[1]
    return _IntervalContainer(start_value, end_value)


def merge_intervals(intervals):
    strategy = _SortingStrategy(key_function=_identity)
    ordered = strategy.perform_sort(intervals)

    merged_containers = collections.deque()

    for raw in ordered:
        container = _normalize_single_interval(raw)
        current_start = container.get_start()
        current_end = container.get_end()

        if len(merged_containers) > 0:
            last_container = merged_containers[-1]
            previous_end = last_container.get_end()
            condition_holds = current_start <= previous_end
        else:
            condition_holds = False

        if condition_holds:
            last_container = merged_containers[-1]
            new_end = _maximum_of_two(last_container.get_end(), current_end)
            last_container.set_end(new_end)
        else:
            fresh = _IntervalContainer(current_start, current_end)
            merged_containers.append(fresh)

    result_accumulator = []
    for stored in merged_containers:
        result_accumulator.append(stored.as_list())

    return result_accumulator
