"""The single home of the oracle-bearing witness-line prefixes (decision 0025).

The multi-file equivalence rejection prints a divergence witness whose two outcome
lines carry the ORACLE: the original's outcome and the candidate's outcome. The
candidate must never see those (Fork 3, decision 0012), so mloop strips exactly
those lines before any feedback reaches the generator.

mevaluator (the producer) formats those lines with the prefixes below, and mloop
(the sanitizer) matches the same prefixes to strip them. Binding both sides to one
definition is the point: a wording change to the producer can no longer silently
defeat the strip, because there is only one string to change and both sides move
together. The real-producer leak test (test_oracle_leak.py) is the standing guard
that fails if these ever drift apart or a rejection is misrouted.

Standard library only; this module imports nothing from mevaluator or mloop, so
neither import is circular.
"""

# Prefix of the line carrying the ORIGINAL (oracle) outcome, and of the line
# carrying the CANDIDATE outcome, in an equivalence-divergence witness. mloop
# matches these after str.strip(); mevaluator emits them indented under the witness.
ORIGINAL_OUTCOME_PREFIX = "original :"
CANDIDATE_OUTCOME_PREFIX = "candidate:"
