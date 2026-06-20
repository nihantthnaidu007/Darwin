from functools import reduce


def average(values):
    if not values:
        return 0.0
    return reduce(lambda a, b: a + b, values, 0) / len(values)
