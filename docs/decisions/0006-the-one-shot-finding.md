# 0006 The one-shot finding

Decision: Single-function optimization is treated as effectively one-shot for a capable model. The feedback loop is verified infrastructure that becomes load-bearing only at larger scope.

Context: On the validation corpus, every improved case (5 of 5) reached its returned-best candidate in generation 1; no case required generation 2 or later. reports/RESULTS.md records this as the headline finding. The loop's demonstrated value at this scope is verification, best-of-N retention, and the never-worse guarantee, not iterative feedback.

Alternatives rejected:
- Claim the multi-generation feedback loop is load-bearing at single-function scope: the generations-used data does not support it.
- Remove the feedback loop: it is expected to matter at multi-file and system scope, where a rewrite cannot be one-shot.

Consequences: Directed feedback is carried as built-and-verified infrastructure into v3 multi-file scope. Results never credit generation 2 or later with a returned result the data attributes to generation 1.
