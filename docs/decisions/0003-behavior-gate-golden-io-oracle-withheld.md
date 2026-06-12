# 0003 Behavior verified by exact golden I/O, oracle withheld

Decision: The behavior gate requires the candidate to reproduce every recorded golden input-to-output pair exactly, with the expected outputs withheld from the candidate.

Context: A candidate is untrusted LLM output. tools/verify_case.py sends only the golden inputs into the container; the in-container driver emits the actual results; this host process holds the expected outputs and does the comparison. The candidate cannot read its own answer key because the answer key is never in the container.

Alternatives rejected:
- Test suite only: the candidate can read test_suite.py and memorize inline expected values.
- Compare inside the container: would place the oracle next to untrusted code.

Consequences: A memorizer is caught whenever the golden inputs are not a subset of the test inputs (a corpus-design mitigation, not OS-enforced). The trusted comparison stays host-side and carries unchanged into the multi-file gate.
