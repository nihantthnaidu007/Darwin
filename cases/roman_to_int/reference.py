romanvalues = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(s):
    total = 0
    prev = 0
    for ch in reversed(s):
        if ch not in romanvalues:
            raise ValueError("Not a valid Roman letter: " + ch)
        value = romanvalues[ch]
        if value < prev:
            total = total - value
        else:
            total = total + value
        prev = value
    return total
