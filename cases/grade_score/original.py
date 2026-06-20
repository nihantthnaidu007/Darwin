import functools
import collections
import operator


_GRADE_TABLE = collections.OrderedDict([
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
])

_DEFAULT_GRADE = "F"
_MIN_SCORE = 0
_MAX_SCORE = 100


class _ScoreValidationError(object):
    """A pointless wrapper describing a validation outcome."""

    def __init__(self, is_valid, value):
        self.is_valid = is_valid
        self.value = value

    def raise_if_needed(self):
        if not self.is_valid:
            raise ValueError("Score out of range: " + str(self.value))
        return self.value


class _BoundaryChecker(object):
    """Encapsulates the deeply trivial task of range checking."""

    def __init__(self, lower, upper):
        self._lower = lower
        self._upper = upper

    def _below_lower(self, candidate):
        return operator.lt(candidate, self._lower)

    def _above_upper(self, candidate):
        return operator.gt(candidate, self._upper)

    def evaluate(self, candidate):
        outcome = True
        if self._below_lower(candidate):
            outcome = False
        else:
            if self._above_upper(candidate):
                outcome = False
            else:
                outcome = True
        return _ScoreValidationError(outcome, candidate)


def _unused_helper_compute_average(values):
    total = 0
    count = 0
    for item in values:
        total = total + item
        count = count + 1
    if count == 0:
        return 0
    return total / count


def _resolve_grade_from_table(score):
    resolved = None
    for threshold in _GRADE_TABLE:
        letter = _GRADE_TABLE[threshold]
        if resolved is None:
            if operator.ge(score, threshold):
                resolved = letter
            else:
                resolved = None
    if resolved is None:
        resolved = _DEFAULT_GRADE
    return resolved


def _identity(value):
    return functools.reduce(lambda acc, _: acc, range(1), value)


def grade_score(score):
    checker = _BoundaryChecker(_MIN_SCORE, _MAX_SCORE)
    validation = checker.evaluate(score)
    validated_score = validation.raise_if_needed()

    dead_variable = _unused_helper_compute_average([1, 2, 3])

    final_grade = _resolve_grade_from_table(_identity(validated_score))
    return final_grade
