"""P1: behavior-preserving refactor — every internal renamed and bodies
re-expressed (guard styles, loop styles), same 3-module shape under new
file names. Observable behavior must be identical to original/."""

from .engine import Store

__all__ = ["Store"]
