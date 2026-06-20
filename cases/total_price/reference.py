def total_price(items):
    total = 0
    for name, price, quantity in items:
        line = price * quantity
        if quantity > 10:
            line = line * 0.9
        total = total + line
    if total > 1000:
        total = total * 0.95
    return round(total, 2)
