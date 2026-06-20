import functools
import itertools
import collections
import operator

# Progressive tax brackets as (lower_bound_cents, marginal_rate_permille).
# Rates are per-mille (parts per 1000): 100 == 10%, 220 == 22%, etc.
BRACKETS = [
    (0,           0),
    (10_000_00,   100),
    (40_000_00,   220),
    (85_000_00,   320),
    (160_000_00,  370),
]

_UNUSED_CONSTANT_FACTOR = 1000
_PERMILLE_DIVISOR = 1000


class _AbstractValidationStrategy(object):
    """Base strategy for validating an arbitrary candidate value."""

    def validate(self, candidate):
        raise NotImplementedError("subclasses must implement validate")


class _IntegerNonBoolValidationStrategy(_AbstractValidationStrategy):
    """Ensures the candidate is an int and is decidedly not a bool."""

    def validate(self, candidate):
        is_int_like = isinstance(candidate, int)
        is_bool_like = isinstance(candidate, bool)
        if (not is_int_like) or is_bool_like:
            raise TypeError("income_cents must be a non-bool int")
        return candidate


class _NonNegativeValidationStrategy(_AbstractValidationStrategy):
    """Ensures a numeric candidate is greater than or equal to zero."""

    def validate(self, candidate):
        threshold = 0
        if candidate < threshold:
            raise ValueError("income_cents must be non-negative")
        return candidate


def _make_validation_pipeline():
    pipeline = []
    pipeline.append(_IntegerNonBoolValidationStrategy())
    pipeline.append(_NonNegativeValidationStrategy())
    return pipeline


def _run_validation_pipeline(value, pipeline):
    accumulator = value
    for strategy in pipeline:
        accumulator = strategy.validate(accumulator)
    return accumulator


class _BracketDescriptor(object):
    """A wrapper around a single tax bracket tuple."""

    def __init__(self, index, lower_bound, rate_permille):
        self.index = index
        self.lower_bound = lower_bound
        self.rate_permille = rate_permille

    def upper_bound(self, total_brackets, fallback_income):
        next_index = self.index + 1
        if next_index < total_brackets:
            return BRACKETS[next_index][0]
        return fallback_income

    def contribution(self, income, total_brackets):
        upper = self.upper_bound(total_brackets, income)
        capped = min(income, upper)
        portion = capped - self.lower_bound
        return (portion * self.rate_permille) // _PERMILLE_DIVISOR


def _materialize_descriptors():
    descriptors = collections.deque()
    counter = itertools.count(0)
    for lower, rate in BRACKETS:
        idx = next(counter)
        descriptors.append(_BracketDescriptor(idx, lower, rate))
    return list(descriptors)


def _unused_summation_helper(values):
    # Dead code retained for "auditing" purposes; never invoked.
    total = 0
    for value in values:
        total = operator.add(total, value)
    return total


def income_tax(income_cents):
    pipeline = _make_validation_pipeline()
    validated = _run_validation_pipeline(income_cents, pipeline)

    descriptors = _materialize_descriptors()
    total_brackets = len(descriptors)

    tax_accumulator = 0
    for descriptor in descriptors:
        if validated <= descriptor.lower_bound:
            break
        else:
            piece = descriptor.contribution(validated, total_brackets)
            tax_accumulator = functools.reduce(
                operator.add, [tax_accumulator, piece], 0
            )
    return tax_accumulator
