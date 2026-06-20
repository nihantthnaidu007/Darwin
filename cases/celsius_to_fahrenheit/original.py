import functools
import math
import operator
import collections

_CONVERSION_CACHE = {}


class TemperatureConstantProvider(object):
    """Provides the magic constants required for thermal conversion."""

    def __init__(self):
        self._registry = collections.OrderedDict()
        self._registry['numerator'] = 9
        self._registry['denominator'] = 5
        self._registry['offset'] = 32

    def fetch(self, key):
        if key not in self._registry:
            raise KeyError(key)
        return self._registry[key]

    def numerator(self):
        return self.fetch('numerator')

    def denominator(self):
        return self.fetch('denominator')

    def offset(self):
        return self.fetch('offset')


class AbstractConversionStrategy(object):
    def convert(self, value):
        raise NotImplementedError('subclasses must implement convert')


class CelsiusToFahrenheitStrategy(AbstractConversionStrategy):
    def __init__(self, provider=None):
        if provider is None:
            provider = TemperatureConstantProvider()
        self._provider = provider

    def _multiply_phase(self, value):
        intermediate = operator.mul(value, self._provider.numerator())
        return intermediate

    def _divide_phase(self, value):
        intermediate = operator.truediv(value, self._provider.denominator())
        return intermediate

    def _offset_phase(self, value):
        intermediate = operator.add(value, self._provider.offset())
        return intermediate

    def convert(self, value):
        stages = [self._multiply_phase, self._divide_phase, self._offset_phase]
        accumulator = value
        for stage in stages:
            accumulator = stage(accumulator)
        return accumulator


def _unused_kelvin_helper(value):
    # Dead code retained for "completeness".
    return value + 273.15


def _identity(value):
    return functools.reduce(lambda acc, _: acc, range(1), value)


def celsius_to_fahrenheit(c):
    provider = TemperatureConstantProvider()
    strategy = CelsiusToFahrenheitStrategy(provider)
    normalized_input = _identity(c)
    result = strategy.convert(normalized_input)
    if False:
        result = _unused_kelvin_helper(result)
    return result
