def classify_triangle(a, b, c):
    if a <= 0 or b <= 0 or c <= 0:
        raise ValueError("Sides must be positive")
    sides = sorted([a, b, c])
    if sides[0] + sides[1] <= sides[2]:
        raise ValueError("Sides do not form a triangle")
    if a == b == c:
        return "equilateral"
    if a == b or b == c or a == c:
        return "isosceles"
    return "scalene"
