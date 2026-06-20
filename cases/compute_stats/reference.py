def compute_stats(numbers):
    if len(numbers) == 0:
        raise ValueError("numbers must not be empty")
    return {
        "min": min(numbers),
        "max": max(numbers),
        "mean": round(sum(numbers) / len(numbers), 4),
    }
