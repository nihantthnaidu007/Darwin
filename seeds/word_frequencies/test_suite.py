from candidate import word_frequencies


def test_empty_string_is_empty_dict():
    # "".split() yields no tokens, so the loop never runs.
    assert word_frequencies("") == {}


def test_whitespace_only_is_empty_dict():
    # split() collapses runs of whitespace and yields nothing for all-whitespace input.
    assert word_frequencies("   \t  \n ") == {}


def test_punctuation_only_tokens_are_skipped():
    # each token strips down to "" and is skipped by the empty-word guard.
    assert word_frequencies("!!! ...") == {}
    assert word_frequencies(".,!? ?!,.") == {}


def test_case_folding_collapses_to_one_key():
    assert word_frequencies("The the THE") == {"the": 3}


def test_surrounding_punctuation_is_stripped_then_counted():
    # leading/trailing .,!? are stripped before counting; interior characters stay.
    assert word_frequencies("the cat, sat. The CAT!") == {"the": 2, "cat": 2, "sat": 1}


def test_repeated_words_accumulate():
    assert word_frequencies("a a a b") == {"a": 3, "b": 1}


def test_only_listed_punctuation_is_stripped():
    # strip(".,!?") removes only those four marks; a trailing semicolon stays part of
    # the word, so "yes;" and "yes" are different keys.
    assert word_frequencies("yes; yes") == {"yes;": 1, "yes": 1}


def test_interior_punctuation_is_preserved():
    # only leading/trailing marks are stripped; an interior period is kept.
    assert word_frequencies("a.b a.b") == {"a.b": 2}
