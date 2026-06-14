"""Planted subtle breaks for the doc_history catch-test."""

BREAKS = [
    # --- gap class 1: dropped validation, every argument-taking method ---
    {"name": "drop_validation_ctor", "gap_class": "validation",
     "file": "docstore.py",
     "old": "        ensure_history_capacity(max_history)\n",
     "new": "",
     "note": "constructor accepts any max_history"},
    {"name": "drop_validation_set", "gap_class": "validation",
     "file": "docstore.py",
     "old": "    def set(self, field, value):\n        ensure_field(field)",
     "new": "    def set(self, field, value):",
     "note": "set() accepts any field key"},
    {"name": "drop_validation_remove", "gap_class": "validation",
     "file": "docstore.py",
     "old": "    def remove(self, field):\n        ensure_field(field)",
     "new": "    def remove(self, field):",
     "note": "remove() accepts any field key (returns False instead of ValueError)"},
    {"name": "drop_validation_get", "gap_class": "validation",
     "file": "docstore.py",
     "old": "    def get(self, field):\n        ensure_field(field)",
     "new": "    def get(self, field):",
     "note": "get() accepts any field key (KeyError instead of ValueError)"},

    # --- gap class 2: deep state (the history cap) ------------------------
    {"name": "deep_cap_off_by_one", "gap_class": "deep_state",
     "file": "journal.py",
     "old": "        if self.depth_mirror > self.capacity:",
     "new": "        if self.depth_mirror >= self.capacity:",
     "note": "journal holds capacity-1 entries (visible only undoing through the cap)"},
    {"name": "deep_undos_counted_when_empty", "gap_class": "deep_state",
     "file": "docstore.py",
     "old": """        operation = self.journal.pop_latest()
        if operation is None:
            return False""",
     "new": """        operation = self.journal.pop_latest()
        if operation is None:
            self.count_undos = self.count_undos + 1
            return False""",
     "note": "failed undo() increments the undos counter (stats-only divergence)"},

    # --- gap class: order dependence --------------------------------------
    {"name": "order_redo_survives_set", "gap_class": "order",
     "file": "docstore.py",
     "old": "        self.journal.push(operation)\n        self.redo_pile.wipe()\n        self.count_sets",
     "new": "        self.journal.push(operation)\n        self.count_sets",
     "note": "set() no longer clears the redo stack"},
    {"name": "order_noop_remove_clears_redo", "gap_class": "order",
     "file": "docstore.py",
     "old": "        if field not in self.data:\n            return False",
     "new": "        if field not in self.data:\n            self.redo_pile.wipe()\n            return False",
     "note": "a no-op remove() now clears redo (must be a FULL no-op)"},
    {"name": "order_undo_overwrite_moves_to_end", "gap_class": "order",
     "file": "operations.py",
     "old": "        if self.had_previous:\n            data[self.field] = self.previous_value",
     "new": "        if self.had_previous:\n            del data[self.field]\n            data[self.field] = self.previous_value",
     "note": "undo of an overwrite re-inserts the field at the end of fields() order"},

    # --- gap class 3: not observable through the API (documented miss) ---
    {"name": "nonobs_trim_archive", "gap_class": "non_observable",
     "file": "journal.py",
     "old": "            del self.entries[0]\n            self.depth_mirror = self.depth_mirror - 1",
     "new": "            self.trim_archive = getattr(self, \"trim_archive\", []); self.trim_archive.append(self.entries[0]); del self.entries[0]\n            self.depth_mirror = self.depth_mirror - 1",
     "note": "trimmed history entries are retained in a shadow archive nothing reads",
     "expect_caught": False},
]
