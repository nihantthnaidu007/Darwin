from candidate import evaluate_postfix


def test_add_then_multiply():
    # (2 + 3) * 4 = 20; the running stack feeds the later operator.
    assert evaluate_postfix(["2", "3", "+", "4", "*"]) == 20


def test_subtraction_operand_order():
    # 5 3 - is 5 - 3 = 2, NOT 3 - 5. left is the deeper pop, right the top pop.
    assert evaluate_postfix(["5", "3", "-"]) == 2


def test_single_number():
    # no operators: the lone operand is pushed and returned.
    assert evaluate_postfix(["7"]) == 7


def test_multiply_then_subtract():
    # 10 2 * 6 - = (10 * 2) - 6 = 14.
    assert evaluate_postfix(["10", "2", "*", "6", "-"]) == 14


def test_nested_right_operand():
    # 1 2 3 * + = 1 + (2 * 3) = 7; the multiply resolves before the add consumes it.
    assert evaluate_postfix(["1", "2", "3", "*", "+"]) == 7


def test_subtraction_can_go_negative():
    # 3 5 - = 3 - 5 = -2; confirms operand order again on a sign-flipping case.
    assert evaluate_postfix(["3", "5", "-"]) == -2
