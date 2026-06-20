def running_max(numbers):
    result = []
    current = None
    for n in numbers:
        if current is None or n > current:
            current = n
        result.append(current)
    return result
