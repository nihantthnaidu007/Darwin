def normalize_scores(scores):
    if not scores:
        return []
    low = min(scores)
    high = max(scores)
    if high == low:
        return [0.0] * len(scores)
    span = high - low
    return [(s - low) / span for s in scores]
