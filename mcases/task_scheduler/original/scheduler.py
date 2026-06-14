"""Scheduler facade wiring guards, job records, and priority buckets."""

from .guards import ValidationEngine, verify_job_id
from .jobs import (
    STATE_CANCELLED,
    STATE_DEAD,
    STATE_DONE,
    STATE_QUEUED,
    STATE_RUNNING,
    JobRecord,
)
from .queues import PriorityBuckets


class Scheduler:
    def __init__(self):
        self.engine = ValidationEngine()
        self.records = {}
        self.queue = PriorityBuckets()
        self.counter_submitted = 0
        self.counter_completed = 0
        self.counter_failed = 0
        self.counter_retried = 0
        self.counter_cancelled = 0
        self.counter_dead = 0

    def _lookup(self, job_id):
        verify_job_id(job_id)
        self.engine.validate("job_id", job_id)
        if job_id not in self.records:
            raise KeyError(job_id)
        record = self.records[job_id]
        return record

    def submit(self, job_id, priority=0, retries=2):
        verify_job_id(job_id)
        self.engine.validate("job_id", job_id)
        self.engine.validate("priority", priority)
        self.engine.validate("retries", retries)
        existing = self.records.get(job_id)
        if existing is not None:
            if existing.is_active():
                raise ValueError("job already active")
        record = JobRecord(job_id, priority, retries)
        self.records[job_id] = record
        self.queue.push(job_id, priority)
        self.counter_submitted = self.counter_submitted + 1
        return None

    def next_job(self):
        job_id = self.queue.pop_best()
        if job_id is None:
            return None
        record = self.records[job_id]
        moved = record.set_state(STATE_RUNNING)
        if not moved:
            # defensive: queue and records disagree; should not happen
            return None
        return job_id

    def complete(self, job_id):
        record = self._lookup(job_id)
        if record.get_state() != STATE_RUNNING:
            raise ValueError("job not running")
        record.set_state(STATE_DONE)
        self.counter_completed = self.counter_completed + 1
        return None

    def fail(self, job_id):
        record = self._lookup(job_id)
        if record.get_state() != STATE_RUNNING:
            raise ValueError("job not running")
        self.counter_failed = self.counter_failed + 1
        remaining = record.retries_remaining()
        if remaining > 0:
            record.consume_retry()
            record.set_state(STATE_QUEUED)
            self.queue.push(job_id, record.priority)
            self.counter_retried = self.counter_retried + 1
            return "requeued"
        record.set_state(STATE_DEAD)
        self.counter_dead = self.counter_dead + 1
        return "dead"

    def cancel(self, job_id):
        record = self._lookup(job_id)
        state = record.get_state()
        if state == STATE_QUEUED:
            removed = self.queue.remove(job_id)
            if not removed:
                # defensive mirror repair; should not happen
                pass
            record.set_state(STATE_CANCELLED)
            self.counter_cancelled = self.counter_cancelled + 1
            return None
        if state == STATE_RUNNING:
            record.set_state(STATE_CANCELLED)
            self.counter_cancelled = self.counter_cancelled + 1
            return None
        raise ValueError("job not active")

    def status(self, job_id):
        record = self._lookup(job_id)
        return record.get_state()

    def pending(self):
        snapshot = self.queue.snapshot()
        result = []
        for job_id in snapshot:
            result.append(job_id)
        return result

    def stats(self):
        running_total = 0
        for job_id in self.records:
            record = self.records[job_id]
            if record.get_state() == STATE_RUNNING:
                running_total = running_total + 1
        payload = {}
        payload["submitted"] = self.counter_submitted
        payload["completed"] = self.counter_completed
        payload["failed"] = self.counter_failed
        payload["retried"] = self.counter_retried
        payload["cancelled"] = self.counter_cancelled
        payload["dead"] = self.counter_dead
        payload["queued"] = self.queue.count()
        payload["running"] = running_total
        return payload
