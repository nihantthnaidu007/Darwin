def parse_time(s):
    parts = s.split(":")
    if len(parts) != 3:
        raise ValueError("Time must have exactly three parts: " + s)
    for part in parts:
        if not part.isdigit():
            raise ValueError("Time part is not a non-negative integer: " + part)
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])
    if hours > 23 or minutes > 59 or seconds > 59:
        raise ValueError("Time field out of range: " + s)
    return hours * 3600 + minutes * 60 + seconds
