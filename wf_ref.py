def word_frequencies(text):
    counts = {}
    for token in text.split():
        word = token.strip(".,!?").lower()
        if word == "":
            continue
        counts[word] = counts.get(word, 0) + 1
    return counts
