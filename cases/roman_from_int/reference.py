romansymbols = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")
]

def roman_from_int(n):
    if n < 1 or n > 3999:
        raise ValueError("Number out of range 1 to 3999: " + str(n))
    result = ""
    for value, symbol in romansymbols:
        while n >= value:
            result = result + symbol
            n = n - value
    return result
