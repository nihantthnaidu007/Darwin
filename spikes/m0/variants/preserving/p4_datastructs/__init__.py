"""P4: behavior-preserving refactor — same module shape as original but
different internal data structures: recency via collections.OrderedDict
(move_to_end) instead of a list, entries as Entry objects instead of
2-element lists. Insertion order for keys() is still carried by the
entries dict. Observable behavior must be identical to original/."""

from .store import Store

__all__ = ["Store"]
