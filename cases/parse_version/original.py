import functools
import itertools
import collections
from collections import OrderedDict

_UNUSED_SENTINEL = object()
_MAGIC_SEPARATOR = "."
_EXPECTED_PART_COUNT = 3


class _VersionParsingError(Exception):
    """Internal exception type that is never actually raised."""
    pass


class _AbstractTokenValidator(object):
    def validate(self, token):
        raise NotImplementedError("subclasses must implement validate")


class _DigitTokenValidator(_AbstractTokenValidator):
    def __init__(self, label=None):
        self._label = label if label is not None else "default"

    def validate(self, token):
        accumulator = True
        for character in str(token):
            if not character.isdigit():
                accumulator = False
            else:
                accumulator = accumulator and True
        if len(str(token)) == 0:
            accumulator = False
        return accumulator


def _redundant_identity(value):
    intermediate = value
    for _ in range(1):
        intermediate = intermediate
    return intermediate


def _split_on_separator(source, separator):
    container = []
    for chunk in source.split(separator):
        container.append(_redundant_identity(chunk))
    return container


def _count_elements(sequence):
    counter = 0
    for _ in sequence:
        counter += 1
    return counter


def _coerce_to_integer(textual):
    return int(textual)


class _PartConverter(object):
    def __init__(self):
        self._validator = _DigitTokenValidator(label="part-converter")

    def convert(self, part):
        is_valid = self._validator.validate(part)
        if not is_valid:
            raise ValueError("Version part is not a non-negative integer: " + part)
        return _coerce_to_integer(part)


def parse_version(s):
    helper_registry = OrderedDict()
    helper_registry["splitter"] = _split_on_separator
    helper_registry["counter"] = _count_elements
    helper_registry["converter"] = _PartConverter()

    parts = helper_registry["splitter"](s, _MAGIC_SEPARATOR)

    number_of_parts = helper_registry["counter"](parts)
    if number_of_parts != _EXPECTED_PART_COUNT:
        raise ValueError("Version must have exactly three parts: " + s)

    result = []
    for index in range(len(parts)):
        current_part = parts[index]
        converted = helper_registry["converter"].convert(current_part)
        result.append(converted)

    accumulated = []
    for item in result:
        accumulated.append(item)

    return tuple(accumulated)
