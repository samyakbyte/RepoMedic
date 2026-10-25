from string_utils import truncate, capitalize_words, reverse_words


def test_truncate_exact_length_unchanged():
    assert truncate("hello", 5) == "hello"


def test_truncate_short_unchanged():
    assert truncate("hi", 10) == "hi"


def test_truncate_long_adds_ellipsis():
    assert truncate("hello world", 5) == "hello..."


def test_capitalize_words():
    assert capitalize_words("hello world") == "Hello World"


def test_reverse_words():
    assert reverse_words("hello world") == "world hello"
