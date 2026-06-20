def total_price(items):
    total = sum(price * qty * 0.9 if qty > 10 else price * qty for _, price, qty in items)
    if total > 1000:
        total = total * 0.95
    return round(total, 2)
