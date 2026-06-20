def categorize_number(n):
    if n < 0:
        return "negative"
    if n == 0:
        return "zero"
    size = "small" if n <= 100 else "large"
    parity = "even" if n % 2 == 0 else "odd"
    return size + " " + parity
