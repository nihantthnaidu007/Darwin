# Security & Threat Model (v1)

**One sentence:** v1 is built to optimize **trusted code you own**, and it
executes LLM-generated candidate code on your machine with only subprocess-level
containment — it is **not** safe for running untrusted or adversarial code.

This document states the boundary plainly and points at the exact code. Nothing
here is hedged: where v1 is exploitable, it says so, and the exploit is pinned by
a test in the repo.

---

## What v1 protects, and what it does not

When the loop evaluates a candidate, that candidate **is executed** (twice: the
`pytest` suite, then the golden-I/O replay). Execution happens in
[tools/sandbox.py](tools/sandbox.py) via `subprocess.Popen` in a fresh temp
directory under a hard wall-clock timeout.

| Property | Status in v1 |
|---|---|
| Orchestrator/evaluator never imports candidate code | **Honored** — the parent process only ever sees the candidate's stdout/stderr + exit code ([verify_case.py](tools/verify_case.py)). |
| Call always returns; temp dir always cleaned up | **Honored** — bounded read + SIGKILL of the child, `rmtree` in a `finally`. |
| Expected (golden) outputs withheld from the sandbox | **Honored** — only inputs are sent in; the parent holds the answer key and compares (`inputs-in / results-out`). |
| Two demonstrated stdout-forgery vectors closed | **Honored** — raw `os.write` to a pre-bound dup of fd 1, random per-run token framing, `os._exit(0)`, fail-closed unless exactly one token frame is present. |
| Robust against **good-faith** (simplification-seeking) candidates | **Yes, by design** — a forgery shim only *adds* complexity, worsening the very score the optimizer is trying to minimize. |
| Forgery-proof against **adversarial** candidates | **NO.** Documented, test-pinned bypass exists (below). |
| OS-level isolation (containers / namespaces / seccomp / cgroups) | **None.** Deferred to v2. |
| CPU / memory resource limits (`rlimit`) | **None.** |
| Network isolation | **None** — candidate has full network access. |
| Filesystem isolation | **None** beyond `cwd = temp dir`; there is no `chroot`/jail, so a candidate can read/write anywhere the invoking user can. |
| Runaway / fork-bomb containment | **Best-effort only** — process-tree kill can be escaped by fast re-parenting, fork bombs, or daemonization. |

**The candidate runs with the full privileges of the invoking OS user.** Treat
running the loop as running arbitrary code *as yourself*.

---

## The core boundary: in-process result handling

The behavior gate works by running, inside the sandbox subprocess, a small trusted
driver that does `import candidate`, calls the entry point, and writes the return
values back to the parent. That driver shares **one OS process** with the
untrusted candidate ([verify_case.py](tools/verify_case.py), the driver source
that emits `import candidate`).

Because the candidate and the trusted result-handling code are co-resident in the
same interpreter, candidate code can reach and replace that handling. The hardening
above closes the two *demonstrated* stdout-forgery paths, but the broader
in-process interposition surface remains open. Three audits concluded that **no
purely in-process scheme closes it**; the real fix is OS-level isolation.

> Note the precision: the candidate shares a process with the *in-sandbox driver*,
> **not** with the orchestrator/evaluator. The orchestrator is protected by the
> subprocess boundary. The forgery risk is about a candidate faking a *passing
> gate result*, not about escaping into the parent process.

### Documented forgery vectors

[tools/test_behavior_gate_limits.py](tools/test_behavior_gate_limits.py)
enumerates three:

1. **`import __main__` serializer hijack** — replace the driver's JSON serializer
   so a behavior-wrong candidate emits forged "correct" results.
2. **`import __main__` writer hijack** — replace the driver's write function.
3. **fd-table rewrite + `sys.excepthook` → `os._exit(0)` + a single forged frame.**

Vector 1 is **executably demonstrated**. The test is marked
`@pytest.mark.xfail(strict=True)`: it asserts the forging candidate is *rejected*,
that assertion **currently fails** (the behavior-wrong candidate is actually
**scored**), so the run reports **`1 xfailed`**. In other words, the bypass works
in v1 today, and it is checked in as an accepted, expected-fail regression marker.
If the gate ever gets hardened, the test will XPASS — the signal to update it.

```bash
cd tools && python -m pytest test_behavior_gate_limits.py -v   # -> 1 xfailed
```

This is why **no part of v1 may be described as "forgery-proof."**

---

## Accepted residual leaks (distinct from forgery)

- **`test_suite.py` is readable by the candidate** inside the Layer-1 `pytest`
  sandbox (pytest needs the file present), and test assertions contain expected
  values inline. A memorizing candidate could hardcode them. This is mitigated
  only by **corpus design** — the golden I/O inputs are not a subset of the test
  inputs, so Layer 2 catches a memorizer — not by any OS-enforced guarantee.
- **On-disk audit logs keep the unstripped reason.** Golden expected outputs are
  stripped from rejection feedback *before it reaches the generator* (Fork 3), but
  the raw "expected R, got R" reason is still written into the per-generation
  records under the gitignored `runs/` directory. The generator never sees it; the
  logs do.

---

## A note on "no forgery observed"

In the good-faith validation runs, every accepted candidate independently
reproduced the golden I/O and none attempted to forge a gate result. That is a
true **observation about good-faith model output** — it is **not** a security
property, and it does not contradict the bypass above. It also cannot be
re-verified from the committed repository: the per-candidate logs live in the
gitignored `runs/` directory and carry no forgery-verdict field. Reproduce by
re-running the harness, not by trusting committed logs.

---

## Secrets

- The only credential is `ANTHROPIC_API_KEY`. It is read from the environment, or
  from a `.env` file at the repository root that is **gitignored and untracked**.
- The key is never hardcoded, logged, or printed
  ([generator.py](tools/generator.py), [bloat.py](tools/bloat.py)). Existing
  environment variables always win over `.env`.
- No secrets are present in any git-tracked file (verified by scanning tracked
  files and full git history for common key patterns). This check is
  pattern-based — strong evidence of absence, not a cryptographic guarantee.

---

## v2: closing the boundary

Safe execution of untrusted code, and a forgery-proof behavior gate, both require
**OS-level isolation** — containers / namespaces / seccomp / cgroups, plus CPU and
memory limits and network restriction. That is the headline v2 work item. Until
then: **only run Darwin on code you trust.**

---

## Reporting

This is a personal research project, not a deployed service. If you find a
security issue beyond the boundaries already documented here, open an issue on the
[repository](https://github.com/nihanthnaidu007/Darwin).
