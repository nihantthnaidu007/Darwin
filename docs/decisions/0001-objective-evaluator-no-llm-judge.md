# 0001 Objective evaluator, no LLM judge

Decision: The correctness gate, the behavior gate, and structural complexity scoring decide whether a candidate is better, with no LLM anywhere in the scoring path.

Context: A self-improving optimizer must not grade its own work by model opinion, or the result is unfalsifiable. tools/evaluator.py runs three layers in strict order and never calls an LLM; tools/verify_case.py runs the gates deterministically.

Alternatives rejected:
- LLM-as-judge of code quality: an unfalsifiable opinion, gameable, and circular for a self-improving loop.
- Single combined score with no hard gates: would let a clean-looking but wrong answer outrank a correct one.

Consequences: Verdicts are reproducible and adversarially defensible. Readability has no objective oracle, so the guards only flag (suspiciously-simple, fragmentation-smell), they never reject.
