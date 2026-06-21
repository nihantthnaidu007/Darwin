# Security & Threat Model — Darwin 1.0 (single-user-trusted)

> **Numbering note.** In this document `v1` and `v2.0` name the **access-isolation
> boundary generations**, not the Darwin release line: `v1` is the retired in-process
> subprocess boundary, and `v2.0` is the current locked-down-container boundary that
> ships in Darwin 1.0. On the release line, **1.0 is current and single-user-trusted**,
> the in-process verdict-forgery boundary is **open by design and deferred to 2.0**
> (decision 0008), and multi-file scope is 3.0. Read every "v2.0 boundary" below as the
> container boundary shipped in Darwin 1.0; nothing here implies 1.0 closes the forgery
> boundary.

**One sentence:** v2.0 runs every candidate inside a **locked-down container**, so
untrusted candidate code can no longer touch your host, network, or secrets — but
the behavior gate is **still not forgery-proof** against adversarial *in-process*
code, the isolation is now CI-verified on **native Linux (Ubuntu, cgroup v2)** as
well as Docker Desktop — though **not** on cgroup v1 or non-Ubuntu distributions —
and the scope is still a single function.

This document states the boundary plainly and points at the exact code. Nothing
here is hedged: where v2.0 is still exploitable, it says so, and the exploit is
pinned by a test in the repo.

---

## What v2.0 closes (the headline win): *access* isolation

When the loop evaluates a candidate, that candidate **is executed** (twice: the
`pytest` correctness gate, then the golden-I/O replay). In v2.0 each execution
happens inside a locked-down Docker container — [src/darwin/sandbox_container.py](src/darwin/sandbox_container.py),
the Phase I0 boundary, with the image in [docker/Dockerfile.sandbox](docker/Dockerfile.sandbox).
The container **is the security boundary**, and it is what `verify_case.py` now
drives ([src/darwin/verify_case.py](src/darwin/verify_case.py)).

The lockdown (each item independently verifiable via
[src/darwin/verify_container_sandbox.py](src/darwin/verify_container_sandbox.py)):

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
  the boundary ([src/darwin/verify_case.py](src/darwin/verify_case.py)). A candidate cannot
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

[tests/test_behavior_gate_limits.py](tests/test_behavior_gate_limits.py) carries
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

## The verdict-emission seam: the 2.0 swap point (decision 0032)

Closing the in-process forgery surface in 2.0 requires moving the trusted verdict
producer **out of the candidate's process**. v1.0 makes that a **one-component swap**
ahead of time, without changing any 1.0 behavior. The loop and the benchmark no
longer call the evaluator directly; they depend on a typed **`VerdictEmitter`** seam
— [src/darwin/verdict_emitter.py](src/darwin/verdict_emitter.py) — with a single method,
`emit(case_dir, candidate_dir, timeout) -> MEvaluation`:

- The **only shipped implementation is `InProcessEmitter`**, the 1.0 default: its
  `emit` produces the verdict in-process by delegating to `mevaluator.evaluate` (it
  **wraps** it; it reimplements no gate, scoring, or equivalence logic). This is
  **byte-identical** to the previous direct call.
- The verdict (`MEvaluation`) is **serializable** — `to_dict` / `from_dict`, lossless
  for both the scored and the rejected shape — so a 2.0 emitter can run the
  evaluation **across a process boundary** and hand the same typed result back.
- Because `mloop.run_loop` and `mbenchmark.run_benchmark` depend only on a
  `VerdictEmitter`, the 2.0 **out-of-process emitter swaps in by replacing this one
  component**, touching no consumer. A test fake implementing the Protocol drives the
  loop to completion on canned verdicts, proving the swap holds
  ([tests/test_verdict_emitter.py](tests/test_verdict_emitter.py)).

**Trust posture.** The in-process default is acceptable at 1.0 **because forging
one's own optimization verdict is pointless** under the single-user-trusted posture
(you have no incentive to cheat your own simplifier; the reward-hack audits found
zero forgery signatures). A **multi-tenant 2.0**, where a forged "pass" is rewarded,
**requires the out-of-process emitter** for forgery resistance. Until then, **A1
in-process verdict forgery is open by design** at 1.0 — the two known-open vectors
pinned as `xfail` (decision 0008, above).

**One protocol, one implementation.** v1.0 ships the interface and exactly
`InProcessEmitter`; no registry, factory, plugin selection, second implementation, or
out-of-process implementation is built now. The out-of-process emitter is *received*
in 2.0, not built here.

---

## Native-Linux verification (CI matrix, cgroup v2)

The container lockdown probe ([src/darwin/verify_container_sandbox.py](src/darwin/verify_container_sandbox.py))
now runs in CI on a matrix of native-Linux runners, so the OS-level lockdown is
exercised on real Linux kernels and Docker daemons, not only on the macOS Docker
Desktop LinuxKit VM. The workflow is
[.github/workflows/isolation.yml](.github/workflows/isolation.yml); its exit code
gates each leg, so a lockdown breach fails CI. See decision 0030.

**What actually ran** (recorded by each leg from `docker info`, `uname -r`, and
`docker --version` — not assumed):

| Runner image | cgroup version | Kernel | Docker | Probe result |
|---|---|---|---|---|
| `ubuntu-22.04` | **v2** | `6.8.0-1052-azure` | `28.0.4` (build b8034c0) | **all 9 guarantees held** (exit 0) |
| `ubuntu-24.04` | **v2** | `6.17.0-1018-azure` | `28.0.4` (build b8034c0) | **all 9 guarantees held** (exit 0) |

Both legs run the **full lockdown argv** (every flag is printed at the top of the
probe output) and pass the whole battery under it. On each leg the probe confirms:

- **Network isolation** — `--network none` holds: both the TCP connect and the DNS
  lookup are blocked.
- **Host-filesystem isolation** — only the single read-only bind mount is visible
  (`/sandbox` lists exactly `candidate.py`); the host path is unreachable.
- **Memory cap enforced via OOM kill** — the flooder is killed by `--memory` (swap
  disabled via `--memory-swap == --memory`): exit `137`, status `CRASHED`, and
  `oom_killed=True`. On both cgroup-v2 legs the `.State.OOMKilled` inspect flag **is**
  set.
- **PID cap** — the fork bomb is contained by `--pids-limit` (blocked after 127
  children) and the call still returns normally.
- **Hard timeout and clean teardown** — an infinite loop is killed at ~the timeout, the
  call returns, and no container or host temp artifact leaks (the cleanup check reports
  zero leaks after the whole battery).
- Applied on every run (present in the printed argv and exercised under the full
  battery): **read-only root filesystem** with an in-RAM `/tmp` tmpfs, **non-root** uid
  `1000:1000`, **all Linux capabilities dropped** (`--cap-drop ALL`), and
  **`--no-new-privileges`**.

**Memory-cap enforcement is version-robust by construction.** It does not depend on the
inspect OOM flag: an OOM is a `SIGKILL` that Docker reports as exit `137` (≥ 128), and
`_classify` maps any exit ≥ 128 to `CRASHED` whether or not `.State.OOMKilled` is set
([src/darwin/sandbox_container.py](src/darwin/sandbox_container.py), `_classify`). On the two
cgroup-v2 legs above the flag happens to be set, but a cgroup configuration that left it
unset would still classify the kill as `CRASHED`. The only version-dependent piece is
the `oom_killed` boolean itself, which reads the inspect flag.

**What this does NOT cover (stated plainly, no overclaiming).** Hosted GitHub runners
are Ubuntu on cgroup v2, so this matrix exercises **cgroup v2 on two Ubuntu versions
only** (two kernels, one Docker version). It does **not** exercise **cgroup v1** or
**non-Ubuntu distributions**. A real cgroup-v1 or alternate-distribution run is a
documented **self-hosted / VM follow-up**, not coverage this CI matrix produced.

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

## Multi-tenant hardening (opt-in, OFF BY DEFAULT at 1.0)

The 1.0 lockdown (cap-drop ALL, no-new-privileges, non-root, read-only root, network
none, memory / CPU / PID caps) is sufficient for the **single-user-trusted 1.0 threat
model**, and **1.0 enables none of the items below by default**. They are
**defense-in-depth guidance for a future multi-tenant deployment**, where untrusted
tenants share a host. Each is off by default; the default `docker run` argv is
byte-identical whether or not you adopt them (P6.4.1, decision 0033).

- **seccomp profile (opt-in path, shipped example).** A syscall filter on top of the
  capability drop. There is now an **opt-in hook**: set
  `DARWIN_SANDBOX_EXTRA_SECURITY_OPTS` (comma-separated `docker run --security-opt`
  values, for example `seccomp=/abs/path/example-sandbox-seccomp.json`) and each entry
  is appended as an **additional** `--security-opt`, never replacing a lockdown flag
  ([src/darwin/sandbox_container.py](src/darwin/sandbox_container.py)). An **example starting
  point** ships at [docker/seccomp/example-sandbox-seccomp.json](docker/seccomp/example-sandbox-seccomp.json)
  — it is an **EXAMPLE, NOT a validated production profile** (it allows by default and
  only denies a curated administrative-syscall set; a production profile should
  default-deny with a validated allowlist). The repo **smoke-tests** only that the
  example does not break a normal python+pytest run; that is a **smoke test, not a
  security validation**. **Validating a production profile against the real workload is
  2.0 work.**
- **daemon-level user-namespace remap.** Mapping container root to an unprivileged host
  uid is **Docker daemon configuration** (`/etc/docker/daemon.json` `userns-remap`, or
  `dockerd --userns-remap`), **not a per-container flag**, so it is **operator-side** and
  cannot be set from this code. It is documented here as recommended multi-tenant
  hardening; **enabling it is deferred to the 2.0 multi-tenant work** and is not done
  here.
- **block-IO and file-size caps.** For multi-tenant fairness and disk-exhaustion
  resistance, add block-IO caps at run time (`--blkio-weight`, or
  `--device-write-bps` / `--device-read-bps`) and a file-size cap
  (`--ulimit fsize=<bytes>`). A writable-area size cap is **already in place** in the
  1.0 default — the only writable mount is the in-RAM tmpfs at `/tmp`, created with a
  fixed `size=64m` ([src/darwin/sandbox_container.py](src/darwin/sandbox_container.py)) — but the
  block-IO and `fsize` caps above are **multi-tenant guidance, off by default at 1.0**.

These are recorded so the multi-tenant posture is on the record. 1.0 ships the seccomp
**opt-in plumbing and a labeled example**, and **documents** the userns and block-IO /
file-size guidance; it does **not** enable any of them by default.

---

## Secrets

- The only credential is `ANTHROPIC_API_KEY`. It is read from the environment, or
  from a `.env` file at the repository root that is **gitignored and untracked**.
  It is never passed into the container.
- The key is never hardcoded, logged, or printed ([src/darwin/generator.py](src/darwin/generator.py),
  [src/darwin/bloat.py](src/darwin/bloat.py)). Existing environment variables always win over
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
| In-process verdict forgery (frame-locals hijack / compute-and-lie) | **OPEN by design** — non-issue for single-user use; matters only for a third-party-trusted verdict; needs a process split, prepared as the `VerdictEmitter` 2.0 swap point (decision 0032; compute-and-lie remains even then) |
| Native-Linux isolation (Ubuntu, cgroup v2) | **CI-verified** — lockdown probe green on `ubuntu-22.04` + `ubuntu-24.04` (both cgroup v2); cgroup v1 and non-Ubuntu **not** exercised (documented self-hosted follow-up) |
| Scope | **Single function** (multi-file is v3.0) |

---

## Reporting

This is a personal research project, not a deployed service. If you find a security
issue beyond the boundaries already documented here, open an issue on the
[repository](https://github.com/nihanthnaidu007/Darwin).
