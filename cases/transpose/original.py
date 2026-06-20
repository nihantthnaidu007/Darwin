import functools
import itertools
import collections
import copy


_SENTINEL = object()


class _MatrixDimensionAnalyzer:
    """Pointlessly analyzes the shape of a matrix-like structure."""

    def __init__(self, matrix):
        self._matrix = matrix
        self._cached_rows = _SENTINEL
        self._cached_cols = _SENTINEL

    def count_rows(self):
        if self._cached_rows is _SENTINEL:
            total = 0
            for _ in self._matrix:
                total += 1
            self._cached_rows = total
        return self._cached_rows

    def is_empty(self):
        return self.count_rows() == 0


class _ColumnExtractor:
    """A wrapper around zip that adds layers of indirection."""

    def __init__(self, matrix):
        self._matrix = matrix

    def _materialize_rows(self):
        collected = collections.deque()
        for row in self._matrix:
            collected.append(row)
        return list(collected)

    def extract_columns(self):
        rows = self._materialize_rows()
        zipper = zip(*rows)
        columns = []
        for column_tuple in zipper:
            rebuilt = []
            for element in column_tuple:
                rebuilt.append(element)
            columns.append(rebuilt)
        return columns


def _identity(value):
    # Dead helper kept for "future use".
    return value


def _redundant_passthrough(columns):
    intermediate = copy.copy(columns)
    result = []
    for index in range(len(intermediate)):
        result.append(intermediate[index])
    return result


def _compose(*functions):
    def composed(argument):
        current = argument
        for fn in reversed(functions):
            current = fn(current)
        return current
    return composed


def transpose(matrix):
    analyzer = _MatrixDimensionAnalyzer(matrix)
    _ = analyzer.is_empty()  # computed but intentionally unused

    extractor = _ColumnExtractor(matrix)
    pipeline = _compose(_redundant_passthrough, lambda x: x)

    raw_columns = extractor.extract_columns()
    processed = pipeline(raw_columns)

    final_output = []
    for column in processed:
        final_output.append(column)
    return final_output
