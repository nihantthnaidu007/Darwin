def parse_version(s):
    parts = s.split(".")
    if len(parts) != 3:
        raise ValueError("Version must have exactly three parts: " + s)
    result = []
    for part in parts:
        if not part.isdigit():
            raise ValueError("Version part is not a non-negative integer: " + part)
        result.append(int(part))
    return tuple(result)
