# Darwin

**A verified Python code simplifier with a never-worse-than-baseline guarantee.**

Darwin takes one working-but-bloated Python function and rewrites it into the
simplest version that *still provably behaves identically* — or returns the
original unchanged if it can't beat it. An LLM proposes rewrites; a deterministic,
LLM-free evaluator decides whether each rewrite is correct, behavior-equivalent,
and structurally simpler. Nothing is accepted on the model's say-so.

**New in v2.0:** every candidate now runs inside a locked-down Docker container
(no network, no host filesystem access, memory/CPU/PID caps, non-root, read-only
root, all capabilities dropped, hard wall-clock timeout). The container is the
security boundary, so running untrusted candidate code can no longer reach your
host, network, or secrets. This is an ***access*-isolation** win; it does **not**
make the behavior gate forgery-proof against adversarial in-process code (see
below).

> **v2.0 is an honest isolation milestone, not a finished product.** Read
> [Scope and limitations](#scope-and-limitations-read-this-first) before anything
> else — it states plainly what v2.0 now closes (untrusted candidate code can no
> longer touch your host, network, or secrets), what it still does *not* do (the
> behavior gate is still **not** forgery-proof against in-process adversarial
> code), the platform caveat (isolation verified on Docker Desktop, **not yet** on
> native Linux), the still-single-function scope, and the key empirical finding.

---

## Scope and limitations (read this first)

These are not footnotes. They are the most important thing to understand about v1.

- **Single function only (unchanged in v2.0).** Each "case" is one Python
  function. v2.0 adds isolation, not scope; it is still single-function
  optimization, which is effectively one-shot for capable models. Multi-file /
  system scope (where the feedback loop becomes load-bearing) is **v3.0**.
- **One-shot in practice.** On the validation corpus, a capable model reaches the
  structural complexity floor in **generation 1** every time (5/5 cases). The
  multi-generation directed-feedback loop is *built and verified to work*, but it
  was **not load-bearing** at single-function scale — later generations added
  zero further reduction. Directed feedback is expected to matter at multi-file /
  system scope, which is deferred to **v3.0**. See
  [reports/RESULTS.md](reports/RESULTS.md).
- **Validated on ~5 cases — a validation set, not a benchmark.** Five hand-built
  cases exercise the engine end to end (in v2.0, every candidate gate run now
  executes inside the container — see [reports/ISOLATION.md](reports/ISOLATION.md)
  for the measured cost). They establish that the machinery works; they are *not*
  a statistically meaningful benchmark. A benchmark-grade claim would need ~25–30
  cases across categories and difficulties (a **v3.0** prerequisite).
- **Untrusted-code *access* isolation (new in v2.0) — but the gate is still NOT
  forgery-proof.** Every candidate now runs inside a locked-down Docker container
  (no network, no host filesystem access, memory/CPU/PID caps, non-root,
  read-only root, all capabilities dropped, no-new-privileges, hard wall-clock
  timeout). This closes the demonstrated **access** vectors: host / network /
  secret access; the golden-oracle read (golden outputs never enter the
  container); the literal `import __main__` driver hijack; and the
  unbounded-output memory risk (memory cap). It is now safe to run a candidate in
  the sense that **the candidate cannot harm your host or reach your secrets.**
  What it does **not** close: the candidate and the trusted result-emitter still
  share **one process *inside* the container**, so an adversarial candidate can
  still forge the behavior-gate verdict in-process (the frame-locals serializer
  hijack — pinned as a known-open `xfail` — or compute-and-lie). The container
  does **not** fix this. *Trigger condition:* it is a non-issue for single-user
  optimization (you have no incentive to forge your own optimization, and the v1
  and I2 reward-hack audits found the optimizer never approaches forgery); it
  matters **only** if the gate's verdict becomes a third-party-trusted artifact
  (a public leaderboard, a certification, a competitive multi-tenant service).
  Closing it then requires an architecture change (splitting the trusted emitter
  out of the candidate's process), and even that leaves compute-and-lie. This is
  deferred by deliberate decision, not overlooked. See [SECURITY.md](SECURITY.md).
- **Platform caveat — native Linux not yet verified.** The isolation was verified
  on macOS / Docker Desktop (a LinuxKit VM, cgroup v2). The guarantees should be
  equal or stronger on native Linux, but native-Linux behavior (OOMKilled
  reporting, cgroup-version-dependent PID / memory cap behavior) has **not** been
  re-confirmed. Re-confirm on native Linux before any production deployment with
  untrusted users. v2.0 does **not** claim production-grade isolation on native
  Linux.
- **"Simpler" means structurally simpler by a fixed metric** (cyclomatic
  complexity, logical LOC, nesting, dependencies, dead code). It makes **no**
  claim about runtime performance, readability, or any property the metric does
  not measure.

What Darwin deliberately is *not*: it is not a "self-evolving agent," not emergent
self-improvement, and — even with v2.0's isolation — not a forgery-proof judge of
adversarial code (it is *access*-safe, not verdict-proof). Those would be
overclaims the evidence does not support.

---

## What it does

For one case, Darwin runs a directed **generate → evaluate → feedback** loop:

1. **Baseline.** It scores the bloated `original.py` as the baseline and keeps it
   as a guaranteed fallback.
2. **Generate.** An LLM proposes one candidate rewrite per generation. The
   generator is **blind to the tests and the golden oracle** — it sees only the
   task description, the original code, and (on later generations) its previous
   attempt plus *sanitized* feedback with expected outputs stripped out.
3. **Evaluate.** Each candidate must pass, in order:
   - a **correctness gate** — the case's `pytest` suite passes; then
   - a **behavior-equivalence gate** — the function reproduces every recorded
     golden input→output pair *exactly* (expected outputs are withheld from the
     sandbox, so the candidate cannot read its own answer key).

   Only candidates that clear **both** gates are scored. Scoring is a fixed
   weighted sum of **structural** metrics (via `radon` + `vulture` + `ast`).
   **No LLM judges code quality** anywhere in the scoring path.
4. **Feedback / stop.** The loop continues until it hits the structural floor, a
   generation cap, or a non-improvement plateau.
5. **Return the best — never worse.** It keeps the lowest-scoring gate-passing
   candidate found. If nothing scores strictly below the baseline, it returns the
   **unmodified original**. The result is therefore never *worse-scoring* than the
   input (by the structural metric).

Two readability guards (`suspiciously-simple`, `fragmentation-smell`) **flag**
golfed or over-fragmented candidates for human review rather than rejecting them —
because there is no objective, LLM-free readability oracle, and rejecting a
genuinely simpler correct answer would violate "objective only."

---

## Install

Darwin is run **from source** (it is not pip-installable yet; see
[pyproject.toml](pyproject.toml)).

Requirements: **Python ≥ 3.10** (developed and validated on **3.13.2**).

```bash
# from the repository root
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt     # radon, vulture, pytest, anthropic (all pinned)
```

**Docker is a prerequisite (new in v2.0).** Candidate code executes inside a
container, so anything that runs a candidate through the gates needs Docker
installed and running, and the sandbox image built once:

```bash
# one-time host setup, from the repository root
docker build -f tools/Dockerfile.sandbox -t darwin-sandbox:py313 tools/
```

Isolation was verified on macOS / Docker Desktop (a LinuxKit VM, cgroup v2);
native-Linux behavior has **not** yet been re-confirmed (see
[SECURITY.md](SECURITY.md)).

**API key (only needed to *run the loop* — i.e. to call the LLM).** Set
`ANTHROPIC_API_KEY` in your environment, or put it in a `.env` file at the
repository root:

```bash
# .env  (already gitignored — never commit it)
ANTHROPIC_API_KEY=sk-ant-...
```

Running the loop makes live Anthropic API calls and incurs real (sub-dollar per
case) token cost. The read-only checks below (`smoke_test.py`, `bakeoff.py`, the
limits test) make **no** API calls and need no key, but they **do** run candidates
through the container, so they require Docker. Only `benchmark.py --report-only`
and `freeze_metrics.py` need neither Docker nor a key.

---

## Usage

The tools are flat scripts with bare imports, so **run them from the `tools/`
directory** using the virtualenv's Python (it has `radon`/`vulture`).

```bash
cd tools

# Optimize one case (calls the LLM; needs an API key). Cases live in ../cases/.
python loop.py sum_evens
python loop.py income_tax --cap 5 --plateau 2 --model claude-opus-4-8
#   -> writes a fresh ../runs/<case>_<UTC>/ with gen_NN.{py,json}, best.py, run.json

# Run the full validation harness over every case in ../cases/ (calls the LLM;
# every gate run executes inside the container), regenerating
# ../reports/aggregate.json and ../reports/RESULTS.md.
python benchmark.py

# Re-render the report from an existing aggregate.json — NO API calls, no Docker.
python benchmark.py --report-only

# Read-only sanity / scoring checks (no API key, but Docker required — they run
# candidates through the container gates):
python smoke_test.py     # runs each case's reference + original through the gates
python bakeoff.py        # compares Layer-3 scoring methods; shows the gaming traps

# Documents the behavior-gate forgery boundary as an executable, expected-fail
# regression marker (Docker required; the gate runs in the container). Expected
# result: "1 xfailed" (see SECURITY.md).
python -m pytest test_behavior_gate_limits.py -v
```

Authoring a new case (clean reference → bloated original → frozen baseline):

```bash
cd tools
python build_case.py ../seeds/<name>          # LLM-bloats the reference, gates it, freezes metrics
python freeze_metrics.py ../cases/<name>/original.py   # structural metrics for one file (no LLM)
```

---

## Results

The committed run is summarized in **[reports/RESULTS.md](reports/RESULTS.md)**
(machine-readable: [reports/aggregate.json](reports/aggregate.json)). Headline
numbers from that run (`claude-opus-4-8`, `cap=5`, `plateau=2`):

| metric | value |
|---|---|
| cases improved over baseline | **5 / 5** |
| baseline returned (nothing beat it) | 0 / 5 |
| improved cases that were **one-shot** (best from generation 1) | **5 / 5** |
| cases that required generation 2+ | **0 / 5** |
| feedback loop load-bearing on this corpus? | **no** |
| total cost (real API token counts) | $0.16157 |

Each "best" candidate passed both gates before being scored, so the reductions
are **verified behavior-preserving** simplifications, not merely smaller code. In
v2.0 the benchmark runs every gate **inside the container**; the measured cost of
that isolation (≈0.17 s fixed per container spin-up, small against LLM latency)
and the cleanup-at-scale and under-isolation reward-hack re-audit are in
**[reports/ISOLATION.md](reports/ISOLATION.md)**.

**Important provenance caveat:** the per-generation candidate logs that back these
numbers live in `runs/`, which is **gitignored**. The committed `reports/` are
derived summaries; to independently verify, **re-run** the harness rather than
trusting committed logs. Results are also a single stochastic LLM run (run-to-run
variance ≈ ±1 generation on at most one case; headline unchanged).

---

## Architecture

```
seeds/        Hand-written case sources: spec.json + clean reference.py + test_suite.py
   │  build_case.py  (bloat.py LLM-bloats the reference, gates it, freezes metrics)
   ▼
cases/        Materialized cases. Each: original.py (bloated input), reference.py
              (clean floor), test_suite.py (correctness gate), golden_io.json
              (behavior gate I/O), baseline_metrics.json (frozen original+floor),
              meta.json (category/difficulty/entry_point)
```

The loop, per generation:

```
loop.py  ──calls──▶  generator.py        one LLM candidate (blind to tests/oracle)
   │                      │
   │                      ▼
   └────────────▶  evaluator.py           Method-A weighted-sum structural score
                          │                (radon/vulture/ast via freeze_metrics.py)
                          ▼
                   verify_case.py          Layer 1 pytest gate, then Layer 2 exact
                          │                golden-I/O gate (expected outputs withheld;
                          │                oracle + comparison stay host-side)
                          ▼
                   sandbox_container.py    locked-down Docker container per gate run
                                           (no network, no host FS, mem/CPU/PID caps,
                                           non-root, read-only root, hard timeout)
```

(The v1 in-process `sandbox.py` primitive is retained in the tree; v2.0 routes the
gates through `sandbox_container.py`, which exposes the same contract across an OS
boundary.)

- **`loop.py`** — orchestrator: baseline, generation cap, plateau rule,
  never-worse fallback, sanitized feedback, per-generation logging to `runs/`.
- **`generator.py`** — single Anthropic API call; extracts/validates one candidate.
- **`evaluator.py`** — Layer 3 objective scoring (fixed weights; `maintainability_index`
  is measured but weight-0 because it is cosmetically gameable; guards flag, never reject).
- **`verify_case.py` / `sandbox_container.py`** — the correctness + behavior gates
  and the locked-down-container sandbox primitive (the v2.0 OS boundary). The
  golden oracle and the result comparison stay host-side, outside the container.
- **`benchmark.py` / `run_summary.py` / `report.py`** — run the loop over the
  corpus and produce `reports/RESULTS.md` + `reports/aggregate.json` from each
  run's own logs (no re-measurement).

---

## Security / threat model

**v2.0 isolates *access*: candidate code runs in a locked-down container and
cannot touch your host, network, or secrets.** That closes the demonstrated
access-based forgery vectors (the golden-oracle read and the literal
`import __main__` driver hijack) plus the unbounded-output memory risk. It does
**not** make the behavior gate forgery-proof: the candidate still shares one
process with the trusted result-emitter *inside* the container, so an adversarial
candidate can still forge the verdict in-process (known-open frame-locals hijack,
or compute-and-lie). That residual matters **only** when the verdict becomes a
third-party-trusted artifact (leaderboard / certification / multi-tenant service);
for single-user optimization it is a non-issue. **Platform caveat:** isolation was
verified on macOS / Docker Desktop, **not yet** on native Linux — re-confirm there
before production with untrusted users. The full model — what the container
closes, the open in-process residual and its trigger condition, the native-Linux
caveat, and optional future hardening — is in **[SECURITY.md](SECURITY.md)**.

---

## Roadmap (v3.0)

v2.0 added the OS-level isolation boundary. The remaining work, in priority order:

- **Native-Linux re-confirmation.** Re-verify the lockdown (OOMKilled reporting,
  cgroup-version-dependent PID / memory caps) on native Linux before any
  production deployment with untrusted users.
- **Split the trusted emitter out of the candidate's process** to close the
  in-process verdict-forgery residual — required *only* if the gate's verdict
  becomes a third-party-trusted artifact (and even then compute-and-lie remains).
- **Multi-file / system scope**, where a rewrite cannot be one-shot and the
  directed multi-generation feedback loop becomes load-bearing.
- **A real benchmark** (~25–30 cases across categories/difficulties) to replace
  the validation set.
- **Optional defense-in-depth** (a custom seccomp profile, user-namespace remap).
  Not required for the current threat model per the I0 audit; noted as a possible
  future hardening only.
