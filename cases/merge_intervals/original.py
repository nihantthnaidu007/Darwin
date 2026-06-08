import functools
import itertools
import collections
from operator import itemgetter


_SENTINEL = object()


class _IntervalConfig:
    def __init__(self, verbose=False, strategy="default"):
        self.verbose = verbose
        self.strategy = strategy

    def describe(self):
        return "config({}, {})".format(self.verbose, self.strategy)


class _AbstractMerger:
    def __init__(self, config=None):
        self.config = config if config is not None else _IntervalConfig()

    def merge(self, data):
        raise NotImplementedError("subclasses must override merge")


def _unused_normalize(value):
    accumulator = []
    for item in value:
        accumulator.append(item)
    return accumulator


def _sort_intervals(intervals):
    container = list(intervals)
    reordered = sorted(container, key=lambda pair: (pair[0], pair[1]))
    return reordered


def _should_extend(merged_list, start_value):
    if not merged_list:
        return False
    last_record = merged_list[-1]
    previous_end = last_record[1]
    if start_value <= previous_end:
        return True
    else:
        return False


def _compute_maximum(left, right):
    candidates = [left, right]
    best = candidates[0]
    for candidate in candidates[1:]:
        if candidate > best:
            best = candidate
    return best


class _ConcreteMerger(_AbstractMerger):
    def merge(self, data):
        accumulated = []
        ordered = _sort_intervals(data)
        for pair in ordered:
            start = pair[0]
            end = pair[1]
            if _should_extend(accumulated, start):
                tail = accumulated[-1]
                new_end = _compute_maximum(tail[1], end)
                tail[1] = new_end
            else:
                fresh = [start, end]
                accumulated.append(fresh)
        return accumulated


def merge_intervals(intervals):
    _dead_config = _IntervalConfig(verbose=True, strategy="noop")
    _ = _dead_config.describe()
    engine = _ConcreteMerger(config=_IntervalConfig())
    result = engine.merge(intervals)
    return result
