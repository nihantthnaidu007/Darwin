def apply_shipping(weight, distance, express):
    cost = weight * 0.5 + distance * 0.1
    if express:
        cost = cost * 1.5
    if cost < 5.0:
        cost = 5.0
    return round(cost, 2)
