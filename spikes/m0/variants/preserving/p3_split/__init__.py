"""P3: behavior-preserving refactor — split further apart: clock and
counters extracted into their own modules (5 files instead of 3).
Observable behavior must be identical to original/."""

from .store import Store

__all__ = ["Store"]
