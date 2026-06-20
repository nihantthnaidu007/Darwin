def apply_discount(price, percent):
    if price < 0:
        raise ValueError("price must not be negative")
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    return round(price * (1 - percent / 100), 2)
