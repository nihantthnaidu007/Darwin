# 0009 Multi-file equivalence via differential testing at the public API

Decision: Multi-file correctness is verified by differential testing at the public API. For the same call sequence, original and candidate must produce identical per-call observables on fresh instances. The guarantee is strong-but-not-total, strictly weaker than single-function golden I/O.

Context: A multi-file unit has internal state, order-dependent behavior, and no single entry point, so there is no enumerable input space to replay. The M0 spike (reports/M0_EQUIVALENCE.md) accepted all 4 behavior-preserving refactors and rejected all 6 subtle behavior-changing ones, and mapped 3 adversarial misses (non-API effects, unreached subdomains, unreached deep states) that more engineering cannot remove. tools/mdiffer.py implements the equivalence core.

Alternatives rejected:
- Golden input-to-output pairs as in v1: there is no single pure entry point for a stateful unit.
- Inspecting private internals: would break black-box equivalence and couple the check to one implementation.

Consequences: The claim language is sequence-relative and API-relative: no divergence observed at the public API over the recorded sequence corpus, not behaves identically on every golden pair. The three gap classes are permanent residents of the threat model, documented per case.
