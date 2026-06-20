def format_phone(digits):
    if len(digits) != 10 or not digits.isdigit():
        raise ValueError("Expected exactly 10 digits: " + digits)
    return "(" + digits[0:3] + ") " + digits[3:6] + "-" + digits[6:10]
