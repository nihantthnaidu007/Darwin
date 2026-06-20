def chunk(items, size):
    result = []
    for i in range(0, len(items), size):
        result.append(items[i:i + size])
    return result
