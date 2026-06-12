"""Undo journal (capacity-bounded) and redo pile, with depth mirrors."""


class Journal:
    def __init__(self, capacity):
        self.capacity = capacity
        self.entries = []
        self.depth_mirror = 0

    def push(self, operation):
        self.entries.append(operation)
        self.depth_mirror = self.depth_mirror + 1
        if self.depth_mirror > self.capacity:
            del self.entries[0]
            self.depth_mirror = self.depth_mirror - 1
        return self.depth_mirror

    def pop_latest(self):
        if self.depth_mirror == 0:
            return None
        self.depth_mirror = self.depth_mirror - 1
        operation = self.entries.pop()
        return operation

    def size(self):
        return self.depth_mirror


class RedoPile:
    def __init__(self):
        self.entries = []

    def push(self, operation):
        self.entries.append(operation)
        return len(self.entries)

    def pop_latest(self):
        if len(self.entries) == 0:
            return None
        return self.entries.pop()

    def wipe(self):
        self.entries = []
        return None

    def size(self):
        return len(self.entries)
