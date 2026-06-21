from candidate import dedupe


def test_empty():
    assert dedupe([]) == []


def test_all_unique_unchanged():
    # nothing to remove; order is preserved exactly.
    assert dedupe([1, 2, 3]) == [1, 2, 3]


def test_all_duplicates_collapse_to_one():
    assert dedupe([1, 1, 1]) == [1]


def test_first_occurrence_order_preserved():
    # the defining property: each value appears once, in the position of its FIRST
    # occurrence. A set()-based dedupe would not guarantee this ordering.
    assert dedupe([3, 1, 2, 1, 3]) == [3, 1, 2]


def test_strings_first_seen_order():
    assert dedupe(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_adjacent_and_distant_duplicates():
    # duplicates both next to and far from their first occurrence collapse the same way.
    assert dedupe([5, 5, 6, 7, 6, 5]) == [5, 6, 7]
