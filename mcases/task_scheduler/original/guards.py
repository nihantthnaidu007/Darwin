"""Input validation layer with a rule engine abstraction."""

import re

ID_MESSAGE = "job_id must be a non-empty string of at most 64 characters"
PRIORITY_MESSAGE = "priority must be an integer between -10 and 10"
RETRIES_MESSAGE = "retries must be an integer between 0 and 5"

ID_MAX_LENGTH = 64
PRIORITY_MINIMUM = -10
PRIORITY_MAXIMUM = 10
RETRIES_MINIMUM = 0
RETRIES_MAXIMUM = 5


class ValidationRule:
    def __init__(self, name, predicate, message):
        self.name = name
        self.predicate = predicate
        self.message = message

    def apply(self, value):
        outcome = self.predicate(value)
        if outcome is not True:
            raise ValueError(self.message)
        return True


class ValidationEngine:
    def __init__(self):
        self.rules = {}
        self.register("job_id", self._job_id_predicate, ID_MESSAGE)
        self.register("priority", self._priority_predicate, PRIORITY_MESSAGE)
        self.register("retries", self._retries_predicate, RETRIES_MESSAGE)

    def register(self, name, predicate, message):
        rule = ValidationRule(name, predicate, message)
        self.rules[name] = rule
        return rule

    @staticmethod
    def _job_id_predicate(value):
        if not isinstance(value, str):
            return False
        if len(value) < 1:
            return False
        if len(value) > ID_MAX_LENGTH:
            return False
        return True

    @staticmethod
    def _priority_predicate(value):
        if isinstance(value, bool):
            return False
        if not isinstance(value, int):
            return False
        if value < PRIORITY_MINIMUM:
            return False
        if value > PRIORITY_MAXIMUM:
            return False
        return True

    @staticmethod
    def _retries_predicate(value):
        if isinstance(value, bool):
            return False
        if not isinstance(value, int):
            return False
        if value < RETRIES_MINIMUM:
            return False
        if value > RETRIES_MAXIMUM:
            return False
        return True

    def validate(self, name, value):
        rule = self.rules.get(name)
        if rule is None:
            return True
        return rule.apply(value)


def verify_job_id(job_id):
    """Standalone duplicate of the engine's job_id rule."""
    if not isinstance(job_id, str):
        raise ValueError(ID_MESSAGE)
    if len(job_id) < 1 or len(job_id) > ID_MAX_LENGTH:
        raise ValueError(ID_MESSAGE)
    return True


def looks_like_identifier(job_id):
    """Heuristic identifier check. Currently unused."""
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_\-]*$", job_id or ""))
