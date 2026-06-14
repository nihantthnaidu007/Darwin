"""Per-client bucket registry with creation-order tracking."""


class BucketState:
    def __init__(self, tokens, created_at):
        self.tokens = tokens
        self.last_touched = created_at
        self.created_at = created_at

    def consume_one(self):
        self.tokens = self.tokens - 1
        return self.tokens


class BucketRegistry:
    def __init__(self):
        self.storage = {}
        self.creation_order = []
        self.population = 0

    def lookup(self, client):
        if client in self.storage:
            return self.storage[client]
        return None

    def create(self, client, tokens, now):
        state = BucketState(tokens, now)
        self.storage[client] = state
        self.creation_order.append(client)
        self.population = self.population + 1
        return state

    def known_clients(self):
        result = []
        for client in self.creation_order:
            result.append(client)
        return result

    def count(self):
        return self.population
