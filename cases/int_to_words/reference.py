ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety"]
SCALES = ["", " thousand", " million", " billion"]
MAX = 999_999_999_999


def _under_1000(n):
    words = []
    if n >= 100:
        words.append(ONES[n // 100] + " hundred")
        n %= 100
    if n >= 20:
        tens = TENS[n // 10]
        words.append(tens + "-" + ONES[n % 10] if n % 10 else tens)
        n = 0
    if n > 0:
        words.append(ONES[n])
    return " ".join(words)


def int_to_words(n):
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be a non-bool int")
    if abs(n) > MAX:
        raise ValueError("n out of supported range")
    if n == 0:
        return "zero"
    if n < 0:
        return "negative " + int_to_words(-n)
    groups = []
    scale = 0
    while n > 0:
        n, rem = divmod(n, 1000)
        if rem:
            groups.append(_under_1000(rem) + SCALES[scale])
        scale += 1
    return " ".join(reversed(groups))
