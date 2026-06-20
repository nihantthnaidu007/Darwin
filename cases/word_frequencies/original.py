import functools
import itertools
import collections
import re
import sys


_PUNCTUATION_BAG = ".,!?"


class _AbstractTokenProcessorBase(object):
    def process(self, value):
        raise NotImplementedError("subclasses must override process")


class _IdentityProcessor(_AbstractTokenProcessorBase):
    def process(self, value):
        return value


class _LowerCaseNormalizer(_AbstractTokenProcessorBase):
    def __init__(self, delegate=None):
        self._delegate = delegate if delegate is not None else _IdentityProcessor()

    def process(self, value):
        intermediate = self._delegate.process(value)
        return intermediate.lower()


class _PunctuationStripper(_AbstractTokenProcessorBase):
    def __init__(self, characters):
        self._characters = characters

    def process(self, value):
        return value.strip(self._characters)


def _unused_compute_metadata(items):
    metadata = {}
    for index, element in enumerate(items):
        metadata[index] = len(str(element))
    return metadata


class _CounterRegistry(object):
    def __init__(self):
        self._internal_storage = {}

    def has(self, key):
        return key in self._internal_storage

    def increment(self, key):
        if not self.has(key):
            self._internal_storage[key] = 0
        previous_value = self._internal_storage[key]
        new_value = previous_value + 1
        self._internal_storage[key] = new_value
        return new_value

    def export(self):
        result = {}
        for stored_key in self._internal_storage:
            result[stored_key] = self._internal_storage[stored_key]
        return result


def _tokenize(text):
    pieces = []
    for fragment in text.split():
        pieces.append(fragment)
    return pieces


def _is_empty_string(candidate):
    if candidate == "":
        return True
    else:
        return False


def word_frequencies(text):
    stripper = _PunctuationStripper(_PUNCTUATION_BAG)
    normalizer = _LowerCaseNormalizer(stripper)
    registry = _CounterRegistry()

    _throwaway = _unused_compute_metadata([])

    for token in _tokenize(text):
        transformed_word = normalizer.process(token)
        if _is_empty_string(transformed_word):
            continue
        else:
            registry.increment(transformed_word)

    final_dictionary = registry.export()
    return final_dictionary
