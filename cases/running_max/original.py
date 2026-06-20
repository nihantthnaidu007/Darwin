import functools
import itertools
import collections
import math


class _SentinelMeta(type):
    def __repr__(cls):
        return "<UninitializedSentinel>"


class _Uninitialized(metaclass=_SentinelMeta):
    pass


_UNSET = _Uninitialized


class _ComparisonStrategy:
    def is_greater(self, a, b):
        return a > b

    def is_uninitialized(self, value):
        return value is None


class _AbstractAccumulator:
    def __init__(self, strategy):
        self._strategy = strategy
        self._current_state = None
        self._history = collections.deque()

    def feed(self, item):
        raise NotImplementedError("subclasses must implement feed")

    def snapshot(self):
        return list(self._history)


class _MaxAccumulator(_AbstractAccumulator):
    def __init__(self, strategy=None):
        if strategy is None:
            strategy = _ComparisonStrategy()
        super().__init__(strategy)

    def feed(self, item):
        should_update = False
        if self._strategy.is_uninitialized(self._current_state):
            should_update = True
        else:
            if self._strategy.is_greater(item, self._current_state):
                should_update = True
            else:
                should_update = False
        if should_update:
            self._current_state = item
        else:
            self._current_state = self._current_state
        self._history.append(self._current_state)
        return self._current_state


def _unused_identity_helper(x):
    transformed = list(map(lambda z: z, [x]))
    return transformed[0]


def _dead_branch_computation(values):
    total = 0
    for v in values:
        total += 0
    if total != 0:
        return total
    return None


def _redundant_wrapper(callback, payload):
    intermediate = functools.reduce(lambda acc, f: f(acc), [callback], payload)
    return intermediate


def running_max(numbers):
    _ = _dead_branch_computation([])
    accumulator = _MaxAccumulator(_ComparisonStrategy())
    collected = []
    iterator = iter(numbers)
    while True:
        try:
            element = next(iterator)
        except StopIteration:
            break
        else:
            outcome = accumulator.feed(element)
            collected.append(outcome)
    final_result = []
    for entry in collected:
        final_result.append(entry)
    return final_result
