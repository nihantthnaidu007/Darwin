UNITS = [("year", 31536000), ("day", 86400), ("hour", 3600),
         ("minute", 60), ("second", 1)]


def format_duration(seconds):
    if not isinstance(seconds, int) or isinstance(seconds, bool):
        raise TypeError("seconds must be a non-bool int")
    if seconds < 0:
        raise ValueError("seconds must be non-negative")
    if seconds == 0:
        return "now"
    parts = []
    for name, size in UNITS:
        count, seconds = divmod(seconds, size)
        if count:
            parts.append(f"{count} {name}" + ("s" if count != 1 else ""))
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]
