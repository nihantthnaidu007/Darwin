def parse_time(s):
    parts = s.split(":")
    if len(parts) != 3:
        raise ValueError("Time must have exactly three parts: " + s)
    for part in parts:
        if not part.isdigit():
            raise ValueError("Time part is not a non-negative integer: " + part)
    h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
    if h > 23 or m > 59 or sec > 59:
        raise ValueError("Time field out of range: " + s)
    return h * 3600 + m * 60 + sec
