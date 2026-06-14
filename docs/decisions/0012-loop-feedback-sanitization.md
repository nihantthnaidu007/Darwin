# 0012 Loop feedback sanitization keeps the oracle from the generator

Decision: The multi-file loop re-sanitizes mevaluator feedback before any of it reaches the generator. Scored feedback is forwarded as-is. An equivalence rejection names only the diverging sequence and call (the input) and never the original's outcome. A fail-closed equivalence rejection forwards the candidate's own replay error. A tests-failed rejection forwards a generic behavior-changed message with no pytest dump. A could-not-run, crashed, or timed-out rejection forwards only a tail of the candidate's own error.

Context: mevaluator reports fully and objectively, so its feedback embeds the oracle in two places: the equivalence witness's original outcome, and the pytest assertion dump. Fork 3 (decision 0003) requires the generator never see the oracle. The single-function loop established the pattern (loop.py format_feedback, input-only); the multi-file loop carries it onto the richer multi-file feedback.

Alternatives rejected:
- Forwarding mevaluator feedback verbatim: leaks the oracle and makes the equivalence result meaningless.
- Sanitizing at the source inside mevaluator: the evaluator's record must stay complete for human audit; trimming for the generator's eyes is the loop's responsibility, not the evaluator's.

Consequences: The sanitizer depends on mevaluator's exact feedback strings, a load-bearing contract recorded in the ledger and guarded by a regression test that builds feedback through the real mevaluator helper. The classifier boundary between tests-failed (suppressed) and could-not-run, crashed, or timed-out (forwarded) is load-bearing and must stay tight.
