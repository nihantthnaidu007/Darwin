from candidate import transpose


def test_empty():
    # no rows: zip(*[]) yields nothing, so the result is the empty matrix.
    assert transpose([]) == []


def test_square_2x2():
    assert transpose([[1, 2], [3, 4]]) == [[1, 3], [2, 4]]


def test_rectangular_2x3_becomes_3x2():
    # a non-square rectangular matrix: columns become rows, dimensions swap.
    assert transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]]


def test_column_vector_3x1_becomes_row_1x3():
    assert transpose([[1], [2], [3]]) == [[1, 2, 3]]


def test_row_vector_1x3_becomes_column_3x1():
    assert transpose([[1, 2, 3]]) == [[1], [2], [3]]


def test_rows_are_lists_not_tuples():
    # zip yields tuples; the comprehension rebuilds each row as a list.
    result = transpose([[1, 2], [3, 4]])
    assert all(isinstance(row, list) for row in result)
