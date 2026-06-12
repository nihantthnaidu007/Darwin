# 0007 Container as the boundary for untrusted execution

Decision: Every candidate executes inside a locked-down Docker container, which is the security boundary for access. In-process anti-forgery patches were abandoned as root-cause unfixable.

Context: Candidates are untrusted LLM code. tools/sandbox_container.py runs them with no network, no host filesystem beyond one read-only bind-mount, memory, CPU, and PID caps, non-root, read-only root, dropped capabilities, no-new-privileges, and a hard wall-clock timeout. The v1 audits concluded the in-process interposition surface is unbounded, so no in-process scheme closes it; the real fix is an OS boundary. SECURITY.md and the threat-model docstring in tools/verify_case.py.

Alternatives rejected:
- In-process hardening of the gate: the interposition surface is unbounded, so patches do not close it.
- The v1 subprocess sandbox alone: best-effort tree-kill, not a real OS boundary; retained but no longer the gate path.

Consequences: The access vectors are closed (host, network, secrets, the oracle read, the literal import __main__ hijack, unbounded output). The candidate cannot harm the host or reach secrets. Each gate run pays container spin-up overhead.
