from collections import Counter


def word_frequencies(text):
    words = [w for w in (t.strip(".,!?").lower() for t in text.split()) if w]
    return Counter(words)
