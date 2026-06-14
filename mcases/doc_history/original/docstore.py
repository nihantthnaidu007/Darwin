"""DocStore facade wiring field rules, operations, and the journals."""

from .fieldrules import ensure_field, ensure_history_capacity
from .journal import Journal, RedoPile
from .operations import RemoveOperation, SetOperation


class DocStore:
    def __init__(self, max_history):
        ensure_history_capacity(max_history)
        self.capacity = max_history
        self.data = {}
        self.journal = Journal(max_history)
        self.redo_pile = RedoPile()
        self.count_sets = 0
        self.count_removes = 0
        self.count_undos = 0
        self.count_redos = 0

    def set(self, field, value):
        ensure_field(field)
        had_previous = field in self.data
        if had_previous:
            previous_value = self.data[field]
        else:
            previous_value = None
        operation = SetOperation(field, value, had_previous, previous_value)
        self.data[field] = value
        self.journal.push(operation)
        self.redo_pile.wipe()
        self.count_sets = self.count_sets + 1
        return None

    def remove(self, field):
        ensure_field(field)
        if field not in self.data:
            return False
        previous_value = self.data[field]
        del self.data[field]
        operation = RemoveOperation(field, previous_value)
        self.journal.push(operation)
        self.redo_pile.wipe()
        self.count_removes = self.count_removes + 1
        return True

    def get(self, field):
        ensure_field(field)
        if field not in self.data:
            raise KeyError(field)
        value = self.data[field]
        return value

    def fields(self):
        names = []
        for field in self.data:
            names.append(field)
        return names

    def undo(self):
        operation = self.journal.pop_latest()
        if operation is None:
            return False
        operation.revert(self.data)
        self.redo_pile.push(operation)
        self.count_undos = self.count_undos + 1
        return True

    def redo(self):
        operation = self.redo_pile.pop_latest()
        if operation is None:
            return False
        operation.replay(self.data)
        self.journal.push(operation)
        self.count_redos = self.count_redos + 1
        return True

    def depth(self):
        report = {}
        report["undo"] = self.journal.size()
        report["redo"] = self.redo_pile.size()
        return report

    def stats(self):
        payload = {}
        payload["sets"] = self.count_sets
        payload["removes"] = self.count_removes
        payload["undos"] = self.count_undos
        payload["redos"] = self.count_redos
        payload["fields"] = len(self.data)
        return payload
