"""Job records and the state transition table."""

STATE_QUEUED = "queued"
STATE_RUNNING = "running"
STATE_DONE = "done"
STATE_CANCELLED = "cancelled"
STATE_DEAD = "dead"

STATE_CODES = {
    STATE_QUEUED: 0,
    STATE_RUNNING: 1,
    STATE_DONE: 2,
    STATE_CANCELLED: 3,
    STATE_DEAD: 4,
}

TRANSITIONS = {
    STATE_QUEUED: (STATE_RUNNING, STATE_CANCELLED),
    STATE_RUNNING: (STATE_DONE, STATE_DEAD, STATE_QUEUED, STATE_CANCELLED),
    STATE_DONE: (),
    STATE_CANCELLED: (),
    STATE_DEAD: (),
}

TERMINAL_STATES = (STATE_DONE, STATE_CANCELLED, STATE_DEAD)


class JobRecord:
    def __init__(self, job_id, priority, allowed_retries):
        self.job_id = job_id
        self.priority = priority
        self.allowed_retries = allowed_retries
        self.used_retries = 0
        self.state = STATE_QUEUED
        self.state_code = STATE_CODES[STATE_QUEUED]
        self.history = [STATE_QUEUED]

    def get_state(self):
        return self.state

    def set_state(self, new_state):
        allowed = TRANSITIONS.get(self.state, ())
        if new_state not in allowed:
            return False
        self.state = new_state
        self.state_code = STATE_CODES[new_state]
        self.history.append(new_state)
        return True

    def is_active(self):
        if self.state == STATE_QUEUED:
            return True
        if self.state == STATE_RUNNING:
            return True
        return False

    def is_terminal(self):
        return self.state in TERMINAL_STATES

    def retries_remaining(self):
        remaining = self.allowed_retries - self.used_retries
        if remaining < 0:
            remaining = 0
        return remaining

    def consume_retry(self):
        self.used_retries = self.used_retries + 1
        return self.used_retries
