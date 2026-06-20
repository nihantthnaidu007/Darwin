def evaluate_postfix(tokens):
    operators = {
        "+": lambda left, right: left + right,
        "-": lambda left, right: left - right,
        "*": lambda left, right: left * right,
    }
    stack = []
    for token in tokens:
        if token in operators:
            right = stack.pop()
            left = stack.pop()
            stack.append(operators[token](left, right))
        else:
            stack.append(int(token))
    return stack.pop()
