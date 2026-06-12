"""Priority job scheduler. This file is the behavioral contract.

Jobs move through states: queued -> running -> done | dead, with
queued -> cancelled, running -> cancelled, and running -> queued (retry).

- Scheduler(): no arguments.
- submit(job_id, priority=0, retries=2) -> None
    job_id: non-empty str of at most 64 chars, else
      ValueError("job_id must be a non-empty string of at most 64 characters").
    priority: int (bool rejected) in [-10, 10], else
      ValueError("priority must be an integer between -10 and 10").
    retries: int (bool rejected) in [0, 5], else
      ValueError("retries must be an integer between 0 and 5").
    If the id exists in a non-terminal state (queued/running):
      ValueError("job already active"). Terminal or unknown ids (re)create
    the record and enqueue at the BACK of the priority class. submitted += 1.
- next_job() -> job_id | None
    Pops the highest-priority queued job; ties break FIFO by enqueue order
    (a retried job re-enters at the back). The job becomes running.
    None when nothing is queued.
- complete(job_id) -> None
    Validates id format; unknown id raises KeyError(job_id); a job not in
    state running raises ValueError("job not running"). running -> done,
    completed += 1.
- fail(job_id) -> "requeued" | "dead"
    Same format/existence/state rules as complete. failed += 1. If the job
    has retries left it re-enters its priority class at the back
    (retried += 1, returns "requeued"); otherwise it is dead
    (dead += 1, returns "dead").
- cancel(job_id) -> None
    Validates id format; unknown raises KeyError(job_id); queued or running
    jobs become cancelled (cancelled += 1); terminal jobs raise
    ValueError("job not active").
- status(job_id) -> "queued"|"running"|"done"|"cancelled"|"dead"
    Validates id format; unknown raises KeyError(job_id).
- pending() -> list of queued job_ids in exact pop order.
- stats() -> {"submitted","completed","failed","retried","cancelled","dead",
    "queued","running"}: cumulative counters, except queued/running which
    are live counts.

Deterministic: no wall clock, no randomness, no hash-order dependence.
"""

_ID_MSG = "job_id must be a non-empty string of at most 64 characters"
_PRIORITY_MSG = "priority must be an integer between -10 and 10"
_RETRIES_MSG = "retries must be an integer between 0 and 5"


def _check_id(job_id):
    if not isinstance(job_id, str) or not 1 <= len(job_id) <= 64:
        raise ValueError(_ID_MSG)


def _check_priority(priority):
    if not isinstance(priority, int) or isinstance(priority, bool) \
            or not -10 <= priority <= 10:
        raise ValueError(_PRIORITY_MSG)


def _check_retries(retries):
    if not isinstance(retries, int) or isinstance(retries, bool) \
            or not 0 <= retries <= 5:
        raise ValueError(_RETRIES_MSG)


class Scheduler:
    def __init__(self):
        self._jobs = {}    # job_id -> {"state", "priority", "allowed", "used"}
        self._queue = []   # (priority, seq, job_id); pop = max priority, min seq
        self._seq = 0
        self._submitted = 0
        self._completed = 0
        self._failed = 0
        self._retried = 0
        self._cancelled = 0
        self._dead = 0

    def _enqueue(self, job_id, priority):
        self._queue.append((priority, self._seq, job_id))
        self._seq += 1

    def _require_running(self, job_id):
        _check_id(job_id)
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job["state"] != "running":
            raise ValueError("job not running")
        return job

    def submit(self, job_id, priority=0, retries=2):
        _check_id(job_id)
        _check_priority(priority)
        _check_retries(retries)
        job = self._jobs.get(job_id)
        if job is not None and job["state"] in ("queued", "running"):
            raise ValueError("job already active")
        self._jobs[job_id] = {"state": "queued", "priority": priority,
                              "allowed": retries, "used": 0}
        self._enqueue(job_id, priority)
        self._submitted += 1
        return None

    def next_job(self):
        if not self._queue:
            return None
        entry = min(self._queue, key=lambda e: (-e[0], e[1]))
        self._queue.remove(entry)
        job_id = entry[2]
        self._jobs[job_id]["state"] = "running"
        return job_id

    def complete(self, job_id):
        job = self._require_running(job_id)
        job["state"] = "done"
        self._completed += 1
        return None

    def fail(self, job_id):
        job = self._require_running(job_id)
        self._failed += 1
        if job["used"] < job["allowed"]:
            job["used"] += 1
            job["state"] = "queued"
            self._enqueue(job_id, job["priority"])
            self._retried += 1
            return "requeued"
        job["state"] = "dead"
        self._dead += 1
        return "dead"

    def cancel(self, job_id):
        _check_id(job_id)
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job["state"] == "queued":
            self._queue = [e for e in self._queue if e[2] != job_id]
        elif job["state"] != "running":
            raise ValueError("job not active")
        job["state"] = "cancelled"
        self._cancelled += 1
        return None

    def status(self, job_id):
        _check_id(job_id)
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job["state"]

    def pending(self):
        ordered = sorted(self._queue, key=lambda e: (-e[0], e[1]))
        return [job_id for _, _, job_id in ordered]

    def stats(self):
        return {
            "submitted": self._submitted,
            "completed": self._completed,
            "failed": self._failed,
            "retried": self._retried,
            "cancelled": self._cancelled,
            "dead": self._dead,
            "queued": len(self._queue),
            "running": sum(1 for j in self._jobs.values()
                           if j["state"] == "running"),
        }
