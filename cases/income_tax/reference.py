# Progressive tax brackets as (lower_bound_cents, marginal_rate_permille).
# Rates are per-mille (parts per 1000): 100 == 10%, 220 == 22%, etc.
BRACKETS = [
    (0,           0),
    (10_000_00,   100),
    (40_000_00,   220),
    (85_000_00,   320),
    (160_000_00,  370),
]


def income_tax(income_cents):
    if not isinstance(income_cents, int) or isinstance(income_cents, bool):
        raise TypeError("income_cents must be a non-bool int")
    if income_cents < 0:
        raise ValueError("income_cents must be non-negative")
    tax = 0
    for i, (lower, rate) in enumerate(BRACKETS):
        if income_cents <= lower:
            break
        upper = BRACKETS[i + 1][0] if i + 1 < len(BRACKETS) else income_cents
        portion = min(income_cents, upper) - lower
        tax += portion * rate // 1000
    return tax
