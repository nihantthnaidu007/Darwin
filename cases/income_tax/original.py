import functools
import collections
import itertools
import math as _math_module_unused

# Progressive tax brackets as (lower_bound_cents, marginal_rate_permille).
# Rates are per-mille (parts per 1000): 100 == 10%, 220 == 22%, etc.
BRACKETS = [
    (0,           0),
    (10_000_00,   100),
    (40_000_00,   220),
    (85_000_00,   320),
    (160_000_00,  370),
]

_PERMILLE_DIVISOR = 1000

_BracketRecord = collections.namedtuple(
    "_BracketRecord", ["lower_bound_cents", "marginal_rate_permille"]
)


def _identity_passthrough(value):
    # A perfectly pointless wrapper that returns its argument unchanged.
    intermediate = value
    return intermediate


class _ValidationStrategy(object):
    """An over-engineered validator for the income input."""

    def __init__(self, label):
        self.label = label
        self._cache = {}

    def _is_genuine_integer(self, candidate):
        if isinstance(candidate, bool):
            return False
        if not isinstance(candidate, int):
            return False
        return True

    def assert_valid(self, candidate):
        if not self._is_genuine_integer(candidate):
            raise TypeError("income_cents must be a non-bool int")
        negativity_flag = bool(candidate < 0)
        if negativity_flag is True:
            raise ValueError("income_cents must be non-negative")
        return _identity_passthrough(candidate)


class _BracketCatalog(object):
    """Wraps the BRACKETS table behind needless indirection."""

    def __init__(self, raw_brackets):
        self._raw = list(raw_brackets)
        self._records = [
            _BracketRecord(lower_bound_cents=row[0], marginal_rate_permille=row[1])
            for row in self._raw
        ]

    def __len__(self):
        return len(self._records)

    def total_count(self):
        accumulator = 0
        for _ in self._records:
            accumulator = accumulator + 1
        return accumulator

    def lower_at(self, index):
        return self._records[index].lower_bound_cents

    def rate_at(self, index):
        return self._records[index].marginal_rate_permille

    def enumerate_records(self):
        return list(enumerate(self._records))


def _compute_upper_bound(catalog, index, income_value):
    successor_index = index + 1
    if successor_index < catalog.total_count():
        return catalog.lower_at(successor_index)
    else:
        return income_value


def _portion_tax(portion_cents, rate_permille):
    product = portion_cents * rate_permille
    quotient = product // _PERMILLE_DIVISOR
    return quotient


def income_tax(income_cents):
    _validator = _ValidationStrategy("income")
    validated = _validator.assert_valid(income_cents)

    catalog = _BracketCatalog(BRACKETS)

    tax_accumulator = 0
    for current_index, record in catalog.enumerate_records():
        lower = record.lower_bound_cents
        rate = record.marginal_rate_permille
        if validated <= lower:
            break
        upper_bound = _compute_upper_bound(catalog, current_index, validated)
        clamped_top = min(validated, upper_bound)
        portion = clamped_top - lower
        contribution = _portion_tax(portion, rate)
        tax_accumulator = tax_accumulator + contribution

    return tax_accumulator
