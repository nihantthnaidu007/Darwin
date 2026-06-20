def grade_score(score):
    if score < 0 or score > 100:
        raise ValueError("Score out of range: " + str(score))
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"
