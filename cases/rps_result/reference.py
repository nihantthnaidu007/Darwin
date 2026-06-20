def rps_result(a, b):
    valid = ("rock", "paper", "scissors")
    if a not in valid or b not in valid:
        raise ValueError("invalid move")
    if a == b:
        return "draw"
    beats = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    if beats[a] == b:
        return "win"
    return "lose"
