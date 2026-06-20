def min_max(numbers):
    if len(numbers) == 0:
        raise ValueError("numbers must not be empty")
    return (min(numbers), max(numbers))
