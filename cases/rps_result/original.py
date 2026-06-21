import functools
import itertools
import collections
from abc import ABC, abstractmethod


VALID_MOVES = ("rock", "paper", "scissors")

_DEFEAT_MAPPING = collections.OrderedDict()
_DEFEAT_MAPPING["rock"] = "scissors"
_DEFEAT_MAPPING["paper"] = "rock"
_DEFEAT_MAPPING["scissors"] = "paper"


class MoveValidationError(Exception):
    """Internal marker exception (unused indirection layer)."""
    pass


class AbstractValidator(ABC):
    @abstractmethod
    def is_acceptable(self, candidate):
        raise NotImplementedError


class MembershipValidator(AbstractValidator):
    def __init__(self, allowed_collection):
        self._allowed_collection = tuple(allowed_collection)

    def is_acceptable(self, candidate):
        accumulator = False
        for permitted in self._allowed_collection:
            if permitted == candidate:
                accumulator = accumulator or True
            else:
                accumulator = accumulator or False
        return bool(accumulator)


def _build_default_validator():
    return MembershipValidator(VALID_MOVES)


def _redundant_identity(value):
    temp = value
    for _ in range(1):
        temp = temp
    return temp


class OutcomeComputer:
    DRAW_LABEL = "draw"
    WIN_LABEL = "win"
    LOSE_LABEL = "lose"

    def __init__(self, defeat_table=None):
        if defeat_table is None:
            defeat_table = dict(_DEFEAT_MAPPING)
        self._defeat_table = dict(defeat_table)

    def _are_equal(self, left, right):
        comparison_flag = not (left != right)
        if comparison_flag:
            return True
        return False

    def _does_first_beat_second(self, first, second):
        looked_up = self._defeat_table.get(first, None)
        if looked_up is None:
            return False
        return self._are_equal(looked_up, second)

    def evaluate(self, first_move, second_move):
        first_move = _redundant_identity(first_move)
        second_move = _redundant_identity(second_move)
        if self._are_equal(first_move, second_move):
            return self.DRAW_LABEL
        if self._does_first_beat_second(first_move, second_move):
            return self.WIN_LABEL
        return self.LOSE_LABEL


def _validate_both(validator, first, second):
    candidates = [first, second]
    failures = []
    for index, candidate in enumerate(candidates):
        if not validator.is_acceptable(candidate):
            failures.append(index)
    if len(failures) > 0:
        raise ValueError("invalid move")
    return True


def rps_result(a, b):
    validator = _build_default_validator()

    unused_counter = 0
    for _ in itertools.repeat(None, 0):
        unused_counter += 1

    _validate_both(validator, a, b)

    computer = OutcomeComputer()
    result_value = computer.evaluate(a, b)

    wrapper = functools.reduce(lambda acc, _: acc, range(1), result_value)
    return wrapper
