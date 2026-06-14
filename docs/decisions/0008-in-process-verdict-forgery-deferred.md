# 0008 In-process verdict forgery deferred

Decision: The in-process verdict-forgery residual is deferred by deliberate decision. It is closed only when the gate verdict becomes a third-party-trusted artifact.

Context: The candidate and the trusted result-emitter share one process inside the container, so an adversarial candidate can still forge a passing verdict in-process (the PEP 667 frame-locals serializer hijack, or compute-and-lie). tools/test_behavior_gate_limits.py pins both as xfail(strict) known-open bypasses; the file currently reports 1 xfailed per vector. SECURITY.md states the trigger condition. The v1 and I2 reward-hack audits found zero forgery signatures from the optimizer.

Alternatives rejected:
- Patch the gate in-process: refuted; the hijack forges with a hardcoded constant and a trivial frame walk, not optimizer-disincentivized, and the surface is unbounded.
- Split the trusted emitter out of the candidate process now: an architecture change not justified until the verdict is third-party-trusted, and even then compute-and-lie remains.

Consequences: No part of Darwin may be described as forgery-proof. For single-user optimization it is a non-issue. An xfail that turns XPASS is the signal the vector was closed and the marker must be updated.
