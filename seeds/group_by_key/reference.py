def group_by_key(pairs):
    result = {}
    for key, value in pairs:
        result.setdefault(key, []).append(value)
    return result
