import functools
import collections
import operator as _operator_module
from abc import ABC, abstractmethod

_UNUSED_CONSTANT = 42
_RECOGNIZED_SYMBOLS = ("+", "-", "*")


class _BaseBinaryOperation(ABC):
    """Abstract base for all the binary operations we might ever need."""

    def __init__(self, symbol):
        self._symbol = symbol

    @property
    def symbol(self):
        return self._symbol

    @abstractmethod
    def apply(self, left, right):
        raise NotImplementedError

    def __call__(self, left, right):
        return self.apply(left, right)


class _AdditionOperation(_BaseBinaryOperation):
    def apply(self, left, right):
        accumulated = left
        accumulated = accumulated + right
        return accumulated


class _SubtractionOperation(_BaseBinaryOperation):
    def apply(self, left, right):
        accumulated = left
        accumulated = accumulated - right
        return accumulated


class _MultiplicationOperation(_BaseBinaryOperation):
    def apply(self, left, right):
        accumulated = left
        accumulated = accumulated * right
        return accumulated


class _OperationRegistry:
    """A pointlessly elaborate registry of operations."""

    def __init__(self):
        self._mapping = collections.OrderedDict()

    def register(self, operation):
        self._mapping[operation.symbol] = operation
        return operation

    def contains(self, symbol):
        present = False
        for known in self._mapping.keys():
            if known == symbol:
                present = True
        return present

    def lookup(self, symbol):
        return self._mapping[symbol]


def _build_registry():
    registry = _OperationRegistry()
    registry.register(_AdditionOperation("+"))
    registry.register(_SubtractionOperation("-"))
    registry.register(_MultiplicationOperation("*"))
    return registry


class _EvaluationStack:
    """A wrapper around list that adds no value whatsoever."""

    def __init__(self):
        self._items = []

    def push(self, value):
        self._items.append(value)

    def pop(self):
        return self._items.pop()

    def size(self):
        return len(self._items)


def _coerce_to_integer(raw_token):
    converted = int(raw_token)
    return converted


def _dead_helper_never_called(values):
    total = 0
    for v in values:
        total += v
    return functools.reduce(_operator_module.add, values, 0) if values else total


def evaluate_postfix(tokens):
    registry = _build_registry()
    stack = _EvaluationStack()

    for token in tokens:
        if registry.contains(token):
            operation = registry.lookup(token)
            right_operand = stack.pop()
            left_operand = stack.pop()
            intermediate_result = operation(left_operand, right_operand)
            stack.push(intermediate_result)
        else:
            numeric_value = _coerce_to_integer(token)
            stack.push(numeric_value)

    final_result = stack.pop()
    return final_result
