"""Reversible operation objects for the journal."""


class SetOperation:
    kind = "set"

    def __init__(self, field, new_value, had_previous, previous_value):
        self.field = field
        self.new_value = new_value
        self.had_previous = had_previous
        self.previous_value = previous_value

    def revert(self, data):
        if self.had_previous:
            data[self.field] = self.previous_value
        else:
            del data[self.field]
        return None

    def replay(self, data):
        data[self.field] = self.new_value
        return None


class RemoveOperation:
    kind = "remove"

    def __init__(self, field, previous_value):
        self.field = field
        self.previous_value = previous_value

    def revert(self, data):
        data[self.field] = self.previous_value
        return None

    def replay(self, data):
        del data[self.field]
        return None
