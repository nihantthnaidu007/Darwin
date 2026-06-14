"""Planted subtle breaks for the rate_limiter catch-test."""

BREAKS = [
    # --- gap class 1: dropped validation, every argument-taking method ---
    {"name": "drop_validation_ctor_rate", "gap_class": "validation",
     "file": "limiter.py",
     "old": "        assert_rate(rate)\n        assert_burst(burst)",
     "new": "        assert_burst(burst)",
     "note": "constructor accepts any rate"},
    {"name": "drop_validation_ctor_burst", "gap_class": "validation",
     "file": "limiter.py",
     "old": "        assert_burst(burst)\n        self.rate_per_tick",
     "new": "        self.rate_per_tick",
     "note": "constructor accepts any burst"},
    {"name": "drop_validation_allow", "gap_class": "validation",
     "file": "limiter.py",
     "old": "    def allow(self, client):\n        assert_client(client)",
     "new": "    def allow(self, client):",
     "note": "allow() accepts any client key"},
    {"name": "drop_validation_remaining", "gap_class": "validation",
     "file": "limiter.py",
     "old": "    def remaining(self, client):\n        assert_client(client)",
     "new": "    def remaining(self, client):",
     "note": "remaining() accepts any client key (KeyError instead of ValueError)"},
    {"name": "drop_validation_reset", "gap_class": "validation",
     "file": "limiter.py",
     "old": "    def reset(self, client):\n        assert_client(client)",
     "new": "    def reset(self, client):",
     "note": "reset() accepts any client key (returns False instead of ValueError)"},
    {"name": "drop_validation_tick", "gap_class": "validation",
     "file": "limiter.py",
     "old": "        assert_tick(n)\n",
     "new": "",
     "note": "tick() accepts zero/negative/bool n"},

    # --- gap class 2: deep state -----------------------------------------
    {"name": "deep_clamp_overshoot", "gap_class": "deep_state",
     "file": "refill.py",
     "old": "        replenished = clamp_to_capacity(replenished, self.capacity)\n        if replenished > self.capacity:\n            replenished = self.capacity\n",
     "new": "        replenished = clamp_to_capacity(replenished, self.capacity + 1)\n        if replenished > self.capacity + 1:\n            replenished = self.capacity + 1\n",
     "note": "refill clamp allows burst+1 tokens (visible only after idle-then-drain)"},
    {"name": "deep_refill_after_consume_check", "gap_class": "deep_state",
     "file": "limiter.py",
     "old": """        self.policy.apply(state, self.clock)
        if state.tokens >= 1:""",
     "new": """        had = state.tokens
        self.policy.apply(state, self.clock)
        if had >= 1:""",
     "note": "allow() consults pre-refill tokens (denies at the exact refill tick)"},

    # --- gap class: order dependence --------------------------------------
    {"name": "order_remaining_stale", "gap_class": "order",
     "file": "limiter.py",
     "old": """        refreshed = self.policy.apply(state, self.clock)
        return refreshed""",
     "new": """        return state.tokens""",
     "note": "remaining() reports stale tokens (no lazy refill on read)"},
    {"name": "order_clients_sorted", "gap_class": "order",
     "file": "buckets.py",
     "old": """    def known_clients(self):
        result = []
        for client in self.creation_order:
            result.append(client)
        return result""",
     "new": """    def known_clients(self):
        result = []
        for client in sorted(self.creation_order):
            result.append(client)
        return result""",
     "note": "active_clients() sorted alphabetically instead of first-touch order"},

    # --- gap class 3: not observable through the API (documented miss) ---
    {"name": "nonobs_reset_stale_last", "gap_class": "non_observable",
     "file": "limiter.py",
     "old": "        state.tokens = self.capacity\n        state.last_touched = self.clock\n        self.total_resets",
     "new": "        state.tokens = self.capacity\n        self.total_resets",
     "note": "reset() leaves last_touched stale; provably unobservable because a "
             "full bucket clamps every later refill to burst regardless of elapsed",
     "expect_caught": False},
]
