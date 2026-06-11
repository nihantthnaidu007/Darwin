# Security & Threat Model (v2.0)

**One sentence:** v2.0 runs every candidate inside a **locked-down container**, so
untrusted candidate code can no longer touch your host, network, or secrets — but
the behavior gate is **still not forgery-proof** against adversarial *in-process*
code, the isolation is verified on Docker Desktop and **not yet** on native Linux,
and the scope is still a single function.

This document states the boundary plainly and points at the exact code. Nothing
here is hedged: where v2.0 is still exploitable, it says so, and the exploit is
pinned by a test in the repo.

---

## What v2.0 closes (the headline win): *access* isolation

When the loop evaluates a candidate, that candidate **is executed** (twice: the
`pytest` correctness gate, then the golden-I/O replay). In v2.0 each execution
happens inside a locked-down Docker container — [tools/sandbox_container.py](tools/sandbox_container.py),
the Phase I0 boundary, with the image in [tools/Dockerfile.sandbox](tools/Dockerfile.sandbox).
The container **is the security boundary**, and it is what `verify_case.py` now
drives ([tools/verify_case.py](tools/verify_case.py)).

The lockdown (each item independently verifiable via
[tools/verify_container_sandbox.py](tools/verify_container_sandbox.py)):

| Control | v2.0 status |
|---|---|
| Network | **none** (`--network none`) |
| Host filesystem | **none** beyond one read-only bind-mount of the per-run dir at `/sandbox`; root FS read-only; only an in-RAM tmpfs is writable |
| Secrets | **unreachable** — no host env, no host FS, no network; the only credential (`ANTHROPIC_API_KEY`) never enters the container |
| Memory | capped, swap disabled (`--memory == --memory-swap`); breach → OOM-killed, reported as `oom_killed` |
| CPU | capped (`--cpus`) |
| Processes / fork bombs | capped (`--pids-limit`) |
| Privileges | non-root (image `USER` + `--user 1000`), all capabilities dropped, `--no-new-privileges` |
| Runaway / hang | hard wall-clock timeout enforced host-side; container `docker rm -f` on every path |
| Cleanup | a `finally` force-removes the container and the host temp dir on every path (verified: zero leaks across a full benchmark) |

**This closes the demonstrated *access* vectors from v1:**

- **Host / network / secret access** — cut off by the container lockdown.
- **The golden-oracle read** — the expected (golden) outputs are **never placed in
  the container**. Only inputs go in; the in-container driver emits the *actual*
  results, and the comparison against the answer key happens **host-side**, outside
  the boundary ([tools/verify_case.py](tools/verify_case.py)). A candidate cannot
  read its own answer key because the answer key is not there.
- **The literal `import __main__` driver hijack** — the v1 in-process driver-hijack
  path is closed by the OS boundary: the trusted comparison no longer runs in the
  candidate's process.
- **The unbounded-output memory risk** — bounded by the memory cap and by writing
  container output to capped host files rather than sharing a pipe.

It is now **safe to run a candidate** in the sense that **the candidate cannot harm
your host or reach your secrets.**

---

## What remains OPEN: in-process verdict forgery

The container walls off **access**. It does **not** split the process *inside* the
container. The in-container driver does `import candidate`, calls the entry point,
and emits the results — and it shares **one OS process** with the untrusted
candidate. Because the candidate and the trusted result-emitter are co-resident in
the same interpreter, an adversarial candidate can still **forge a passing verdict
in-process**, two ways:

1. **Frame-locals serializer hijack** — reach into the driver's frame and replace
   the serializer / write path so a behavior-wrong candidate emits forged
   "correct" results. Pinned as a **known-open** vector below.
2. **Compute-and-lie** — compute the correct outputs (the inputs are necessarily in
   the container), emit them, while the candidate's *declared* entry point is
   actually wrong. The container cannot distinguish a correct emission produced by
   honest code from one produced by a liar.

> Precision: this is a candidate faking a *passing gate result*, **not** an escape
> from the container into the host. Access is closed; the verdict is not.

### Trigger condition — when this actually matters

- **Single-user optimization (the actual use case): non-issue.** You have no
  incentive to forge your own optimization. Empirically, the v1 and the I2
  under-isolation reward-hack audits scanned every candidate the optimizer produced
  and found **zero** forgery signatures ([reports/ISOLATION.md](reports/ISOLATION.md));
  the optimizer never approaches the in-process forgery surface, because a forgery
  shim only *adds* complexity and worsens the very score it is trying to minimize.
- **It becomes relevant ONLY if the gate's verdict becomes a third-party-trusted
  artifact** — a public leaderboard, a certification, or a competitive multi-tenant
  service, where an adversary is rewarded for a forged "pass."

Closing it then requires an **architecture change**: splitting the trusted emitter
out of the candidate's process (so the candidate never shares an interpreter with
the code that reports the verdict). Even that leaves **compute-and-lie**, which no
process split alone defeats. This split is **deferred by deliberate decision**,
justified by the audit evidence above — not overlooked.

### The known-open vector is pinned by a test

[tools/test_behavior_gate_limits.py](tools/test_behavior_gate_limits.py) carries
the frame-locals serializer hijack as an executable, expected-fail regression
marker (`@pytest.mark.xfail(strict=True)`): it asserts the forging candidate is
*rejected*, that assertion **currently fails** (the behavior-wrong candidate is
actually scored), so the run reports **`1 xfailed`**. If the gate is ever hardened
to split the emitter out, the test will XPASS — the signal to update it.

```bash
cd tools && python -m pytest test_behavior_gate_limits.py -v   # -> 1 xfailed (Docker required)
```

This is why **no part of Darwin may be described as "forgery-proof."**

---

## Platform caveat: native Linux not yet verified

The isolation was verified on **macOS / Docker Desktop** — a LinuxKit VM, cgroup
v2. The guarantees should be **equal or stronger** on native Linux, but
native-Linux behavior has **not** been re-confirmed, specifically:

- OOMKilled reporting (how the memory-cap kill surfaces),
- cgroup-version-dependent PID / memory cap behavior.

**Re-confirm the lockdown on native Linux before any production deployment with
untrusted users.** v2.0 does **not** claim production-grade isolation on native
Linux.

---

## Accepted residual leaks (distinct from forgery)

- **`test_suite.py` is readable by the candidate** inside the Layer-1 `pytest`
  container (pytest needs the file present), and test assertions contain expected
  values inline. A memorizing candidate could hardcode them. This is mitigated only
  by **corpus design** — the golden I/O inputs are not a subset of the test inputs,
  so Layer 2 catches a memorizer — not by any OS-enforced guarantee.
- **On-disk audit logs keep the unstripped reason.** Golden expected outputs are
  stripped from rejection feedback *before it reaches the generator*, but the raw
  "expected R, got R" reason is still written into the per-generation records under
  the gitignored `runs/` directory. The generator never sees it; the logs do.

---

## Optional future hardening (noted, not built)

The I0 audit concluded the current lockdown (cap-drop ALL, no-new-privs, non-root,
read-only root, network none, memory / CPU / PID caps) is sufficient for the v2.0
threat model. Two items would add **defense-in-depth** but are **not required**, and
are deliberately **not built** in v2.0:

- a **custom seccomp profile** (tighter syscall surface than the Docker default),
- **user-namespace remap** (container root mapped to an unprivileged host uid).

These are possible future hardening, listed so the omission is on the record, not
an oversight.

---

## Secrets

- The only credential is `ANTHROPIC_API_KEY`. It is read from the environment, or
  from a `.env` file at the repository root that is **gitignored and untracked**.
  It is never passed into the container.
- The key is never hardcoded, logged, or printed ([tools/generator.py](tools/generator.py),
  [tools/bloat.py](tools/bloat.py)). Existing environment variables always win over
  `.env`.
- No secrets are present in any git-tracked file (verified by scanning tracked
  files and full git history for common key patterns). This check is pattern-based
  — strong evidence of absence, not a cryptographic guarantee.

---

## Summary of the v2.0 boundary

| Concern | v2.0 |
|---|---|
| Candidate reaches host FS / network / secrets | **Closed** (container lockdown) |
| Golden-oracle read | **Closed** (golden outputs never enter the container) |
| `import __main__` driver hijack | **Closed** (trusted comparison is host-side) |
| Unbounded-output memory exhaustion | **Closed** (memory cap + capped host-file capture) |
| In-process verdict forgery (frame-locals hijack / compute-and-lie) | **OPEN** — non-issue for single-user use; matters only for a third-party-trusted verdict; needs a process split (and even then compute-and-lie remains) |
| Native-Linux production-grade isolation | **Not yet verified** — re-confirm before production |
| Scope | **Single function** (multi-file is v3.0) |

---

## Reporting

This is a personal research project, not a deployed service. If you find a security
issue beyond the boundaries already documented here, open an issue on the
[repository](https://github.com/nihanthnaidu007/Darwin).
