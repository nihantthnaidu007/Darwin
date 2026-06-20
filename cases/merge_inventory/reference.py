def merge_inventory(a, b):
    merged = {}
    for name in a.keys() | b.keys():
        total = a.get(name, 0) + b.get(name, 0)
        if total > 0:
            merged[name] = total
    return merged
