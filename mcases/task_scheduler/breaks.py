"""Planted subtle breaks for the task_scheduler catch-test.

Each break is one exact-match patch applied to a copy of original/ by
validate_mcase.py. expect_caught=False marks the documented irreducible
boundary (M0 gap class 3: not observable through the API).
"""

BREAKS = [
    # --- gap class 1: dropped validation, one break per public method ----
    {"name": "drop_validation_submit_id", "gap_class": "validation",
     "file": "scheduler.py",
     "old": """    def submit(self, job_id, priority=0, retries=2):
        verify_job_id(job_id)
        self.engine.validate("job_id", job_id)
        self.engine.validate("priority", priority)""",
     "new": """    def submit(self, job_id, priority=0, retries=2):
        self.engine.validate("priority", priority)""",
     "note": "submit() accepts any job_id (format checks gone)"},
    {"name": "drop_validation_submit_priority", "gap_class": "validation",
     "file": "scheduler.py",
     "old": '        self.engine.validate("priority", priority)\n        self.engine.validate("retries", retries)',
     "new": '        self.engine.validate("retries", retries)',
     "note": "submit() accepts any priority"},
    {"name": "drop_validation_submit_retries", "gap_class": "validation",
     "file": "scheduler.py",
     "old": '        self.engine.validate("retries", retries)\n        existing',
     "new": '        existing',
     "note": "submit() accepts any retries"},
    {"name": "drop_validation_complete", "gap_class": "validation",
     "file": "scheduler.py",
     "old": """    def complete(self, job_id):
        record = self._lookup(job_id)""",
     "new": """    def complete(self, job_id):
        if job_id not in self.records:
            raise KeyError(job_id)
        record = self.records[job_id]""",
     "note": "complete() skips id format validation (KeyError instead of ValueError on bad ids)"},
    {"name": "drop_validation_fail", "gap_class": "validation",
     "file": "scheduler.py",
     "old": """    def fail(self, job_id):
        record = self._lookup(job_id)""",
     "new": """    def fail(self, job_id):
        if job_id not in self.records:
            raise KeyError(job_id)
        record = self.records[job_id]""",
     "note": "fail() skips id format validation"},
    {"name": "drop_validation_cancel", "gap_class": "validation",
     "file": "scheduler.py",
     "old": """    def cancel(self, job_id):
        record = self._lookup(job_id)""",
     "new": """    def cancel(self, job_id):
        if job_id not in self.records:
            raise KeyError(job_id)
        record = self.records[job_id]""",
     "note": "cancel() skips id format validation"},
    {"name": "drop_validation_status", "gap_class": "validation",
     "file": "scheduler.py",
     "old": """    def status(self, job_id):
        record = self._lookup(job_id)""",
     "new": """    def status(self, job_id):
        if job_id not in self.records:
            raise KeyError(job_id)
        record = self.records[job_id]""",
     "note": "status() skips id format validation"},

    # --- gap class 2: deep state ----------------------------------------
    {"name": "deep_extra_retry", "gap_class": "deep_state",
     "file": "scheduler.py",
     "old": "        if remaining > 0:",
     "new": "        if remaining >= 0:",
     "note": "off-by-one grants one extra retry before dead (visible only at exhaustion)"},
    {"name": "uncommon_cancel_running_counter", "gap_class": "deep_state",
     "file": "scheduler.py",
     "old": """        if state == STATE_RUNNING:
            record.set_state(STATE_CANCELLED)
            self.counter_cancelled = self.counter_cancelled + 1
            return None""",
     "new": """        if state == STATE_RUNNING:
            record.set_state(STATE_CANCELLED)
            return None""",
     "note": "cancelling a RUNNING job stops counting (queued cancels still count)"},

    # --- gap class: order dependence -------------------------------------
    {"name": "order_lifo_tie_break", "gap_class": "order",
     "file": "queues.py",
     "old": """                job_id = bucket[0]
                del bucket[0]""",
     "new": """                job_id = bucket[-1]
                del bucket[-1]""",
     "note": "ties pop LIFO instead of FIFO within a priority class"},
    {"name": "order_requeue_to_front", "gap_class": "order",
     "file": "scheduler.py",
     "old": "            self.queue.push(job_id, record.priority)\n            self.counter_retried",
     "new": "            self.queue.buckets.setdefault(record.priority, []).insert(0, job_id); self.queue.index[job_id] = record.priority; self.queue.total += 1\n            self.counter_retried",
     "note": "retried jobs jump the FIFO line (front of class instead of back)"},

    # --- gap class 3: not observable through the API (documented miss) ---
    {"name": "nonobs_history_dropped", "gap_class": "non_observable",
     "file": "jobs.py",
     "old": "        self.history.append(new_state)\n",
     "new": "",
     "note": "internal write-only history stops recording; no API output exposes it",
     "expect_caught": False},
]
