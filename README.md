# Darwin

**A verified Python code simplifier with a never-worse-than-baseline guarantee.**

Darwin takes one working-but-bloated Python function and rewrites it into the
simplest version that *still provably behaves identically* — or returns the
original unchanged if it can't beat it. An LLM proposes rewrites; a deterministic,
LLM-free evaluator decides whether each rewrite is correct, behavior-equivalent,
and structurally simpler. Nothing is accepted on the model's say-so.

> **v1 is an honest milestone, not a finished product.** Read
> [Scope and limitations](#scope-and-limitations-read-this-first) before anything
> else — it states plainly what v1 does *not* do, the key empirical finding, and
> the trusted-code-only threat model.

---

## Scope and limitations (read this first)

These are not footnotes. They are the most important thing to understand about v1.

- **Single function only.** Each "case" is one Python function. v1 has no
  multi-file or cross-module scope.
- **One-shot in practice.** On the validation corpus, a capable model reaches the
  structural complexity floor in **generation 1** every time (5/5 cases). The
  multi-generation directed-feedback loop is *built and verified to work*, but it
  was **not load-bearing** at single-function scale — later generations added
  zero further reduction. Directed feedback is expected to matter at multi-file /
  system scope, which is deferred to v2. See
  [reports/RESULTS.md](reports/RESULTS.md).
- **Validated on ~5 cases — a validation set, not a benchmark.** Five hand-built
  cases exercise the engine end to end. They establish that the machinery works;
  they are *not* a statistically meaningful benchmark. A benchmark-grade claim
  would need ~25–30 cases across categories and difficulties (a v2 prerequisite).
- **Trusted code only — NOT hardened for untrusted input.** v1 runs candidate
  code in a subprocess sandbox (temp dir + timeout), but that subprocess shares
  its OS process with the trusted result-handling driver, and the candidate runs
  with **your** filesystem and network access. The behavior gate is robust
  against good-faith simplification but is **not forgery-proof** against
  adversarial code — a working in-process bypass is documented and pinned by a
  test. Do not point v1 at code you don't trust. See [SECURITY.md](SECURITY.md).
- **"Simpler" means structurally simpler by a fixed metric** (cyclomatic
  complexity, logical LOC, nesting, dependencies, dead code). It makes **no**
  claim about runtime performance, readability, or any property the metric does
  not measure.

What v1 deliberately is *not*: it is not a "self-evolving agent," not emergent
self-improvement, and not safe for running strangers' code. Those would be
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

v1 is run **from source** (it is not pip-installable yet; see
[pyproject.toml](pyproject.toml)).

Requirements: **Python ≥ 3.10** (developed and validated on **3.13.2**).

```bash
# from the repository root
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt     # radon, vulture, pytest, anthropic (all pinned)
```

**API key (only needed to *run the loop* — i.e. to call the LLM).** Set
`ANTHROPIC_API_KEY` in your environment, or put it in a `.env` file at the
repository root:

```bash
# .env  (already gitignored — never commit it)
ANTHROPIC_API_KEY=sk-ant-...
```

Running the loop makes live Anthropic API calls and incurs real (sub-dollar per
case) token cost. The read-only commands below (`--report-only`, `smoke_test.py`,
`bakeoff.py`, the limits test) make **no** API calls and need no key.

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

# Run the full validation harness over every case in ../cases/ (calls the LLM),
# regenerating ../reports/aggregate.json and ../reports/RESULTS.md.
python benchmark.py

# Re-render the report from an existing aggregate.json — NO API calls, no cost.
python benchmark.py --report-only

# Read-only sanity / scoring checks (no API key, no cost):
python smoke_test.py     # runs each case's reference + original through the gates
python bakeoff.py        # compares Layer-3 scoring methods; shows the gaming traps

# Documents the behavior-gate forgery boundary as an executable, expected-fail
# regression marker. Expected result: "1 xfailed" (see SECURITY.md).
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
are **verified behavior-preserving** simplifications, not merely smaller code.

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
                          │                golden-I/O gate (expected outputs withheld)
                          ▼
                   sandbox.py              subprocess in a temp dir, hard timeout,
                                           best-effort process-tree kill
```

- **`loop.py`** — orchestrator: baseline, generation cap, plateau rule,
  never-worse fallback, sanitized feedback, per-generation logging to `runs/`.
- **`generator.py`** — single Anthropic API call; extracts/validates one candidate.
- **`evaluator.py`** — Layer 3 objective scoring (fixed weights; `maintainability_index`
  is measured but weight-0 because it is cosmetically gameable; guards flag, never reject).
- **`verify_case.py` / `sandbox.py`** — the correctness + behavior gates and the
  OS sandbox primitive.
- **`benchmark.py` / `run_summary.py` / `report.py`** — run the loop over the
  corpus and produce `reports/RESULTS.md` + `reports/aggregate.json` from each
  run's own logs (no re-measurement).

---

## Security / threat model

**v1 is designed to optimize trusted code you own.** It executes LLM-generated
candidate code on your machine with only subprocess-level containment, the
behavior gate is not forgery-proof against adversarial candidates, and a candidate
runs with your filesystem and network access. Safe execution of *untrusted* code
requires OS-level isolation, which is deferred to v2. The full boundary —
including the documented, test-pinned in-process forgery bypass — is in
**[SECURITY.md](SECURITY.md)**. Read it before running this on anything you didn't
write.

---

## Roadmap (v2)

v1 is the honest, scoped foundation. v2 targets the two boundaries that make this
useful in the real world:

- **OS-level isolation** (containers / namespaces / seccomp / resource limits) so
  candidate code can be run safely — the prerequisite for handling untrusted code
  and for closing the behavior-gate forgery boundary.
- **Multi-file / system scope**, where a rewrite cannot be one-shot and the
  directed multi-generation feedback loop becomes load-bearing.
- **A real benchmark** (~25–30 cases across categories/difficulties) to replace
  the v1 validation set.
