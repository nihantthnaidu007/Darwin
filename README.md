<p align="center">
  <img src="assets/darwin-banner.svg" alt="Darwin" width="100%">
</p>

<h1 align="center">Darwin</h1>

<p align="center">
  <a href="reports/RESULTS.md">Findings</a> ·
  <a href="docs/authoring-a-case.md">Author a case</a> ·
  <a href="SECURITY.md">Threat model</a> ·
  <a href="docs/decisions/">Decision log</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-22D3EE?style=for-the-badge" alt="License: Apache 2.0"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.12_–_3.14-22D3EE?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12 to 3.14"></a>
  <img src="https://img.shields.io/badge/Version-1.0.0-06B6D4?style=for-the-badge" alt="Version 1.0.0">
  <img src="https://img.shields.io/badge/Posture-single--user--trusted-0E7490?style=for-the-badge" alt="Single-user-trusted">
  <img src="https://img.shields.io/badge/Verdict-self--verifying-67E8F9?style=for-the-badge" alt="Self-verifying">
</p>

**A self-verifying Python code optimizer and reproducible benchmark, single-user-trusted.** Darwin takes one working-but-bloated Python unit, asks a model to simplify it, and accepts a candidate **only** if it survives objective verification — correctness, behavior-equivalence on frozen golden I/O, and a never-worse-than-baseline structural guarantee. Nothing is accepted on the model's say-so. Every candidate is checked, not trusted.

It is built to **study and reproduce** that behavior on a controlled corpus, not to run on untrusted code and trust the verdict. The verdict is honest because it comes from objective checks an LLM never touches — and the project says so out loud, including where its own scorer has limits.

<table>
<tr><td><b>The model never grades its own work</b></td><td>The verdict comes from objective gates, not the model's judgment: a correctness gate, behavior-equivalence against frozen golden I/O, and a structural-complexity score computed with <b>no LLM in the loop</b>. Most LLM tooling lets the model evaluate its own output. Darwin structurally cannot.</td></tr>
<tr><td><b>Never worse than baseline, by construction</b></td><td>A rewrite is returned only if it is provably no worse than the original on objective metrics. If nothing beats the baseline, the unmodified original is returned. The engine cannot ship a regression.</td></tr>
<tr><td><b>Integrity proven, not asserted</b></td><td>Every one of the 30 benchmark cases was committed to git <b>before</b> it was ever run, and the committed code is byte-identical to what was scored across all 150 runs. No case could be selected or tuned after its results were known. Every published number traces to one committed dataset.</td></tr>
<tr><td><b>Runs untrusted candidates in a locked-down sandbox</b></td><td>Every candidate executes inside a Docker container with no network, no host filesystem, memory/CPU/PID caps, non-root, read-only root, all capabilities dropped, and a hard timeout. The oracle and the comparison stay outside the container, so a candidate cannot read its own answer key.</td></tr>
<tr><td><b>Extendable by anyone</b></td><td>The stable surface is six console scripts, the case directory format, and the dataset JSON schema. A new benchmark case can be authored from <a href="docs/authoring-a-case.md">one guide</a> without reading the engine source.</td></tr>
<tr><td><b>It discloses its own limits</b></td><td>Where the structural scorer can be gamed, the results say so plainly. The findings report exactly what the evidence supports and nothing more — including that the feedback loop is mostly <i>not</i> load-bearing.</td></tr>
</table>

---

## The finding

A 30-case single-function corpus across seven degradation categories, run 5 times each (**150 runs**) under one frozen config (`claude-opus-4-8`, `cap=5`, `plateau=2`, every gate run inside the container). Each case is a clean reference I authored by hand, then degraded into a bloated input the engine has to simplify back down.

| metric | value |
|---|---|
| cases / runs | 30 cases (7 categories) / 150 runs |
| reached the best candidate in generation 1 (one-shot) | **143 / 150 = 95.3%** |
| `best_gen` distribution | gen 1: 143 · gen 2: 4 · gen 3: 3 |
| every run improved over baseline | 150 / 150 |
| feedback loop load-bearing here? | **no** |
| total cost (real API tokens) | $2.60 |

Optimization was effectively **one-shot**: a capable model reaches the structural floor in the first generation 95.3% of the time. The directed multi-generation loop is built and verified, but it is **not load-bearing** at single-function scope — the few later-generation recoveries are run-to-run variance near the floor, not a property of function shape. The loop's real value here is the gates, best-of-N retention, and the never-worse guarantee, not iterative improvement.

Full findings, including the multi-file results and every disclosed limitation, are in **[reports/RESULTS.md](reports/RESULTS.md)** (machine-readable: [reports/v0.9-dataset.json](reports/v0.9-dataset.json)). Every case was provably frozen before it ran — see **[reports/v0.9-temporal-freeze.md](reports/v0.9-temporal-freeze.md)**.

---

## How it works

For one case, Darwin runs a directed **generate → evaluate → feedback** loop:

1. **Baseline.** Score the bloated input and keep it as a guaranteed fallback.
2. **Generate.** An LLM proposes one candidate per generation. The generator is **blind to the tests and the oracle** — it sees only the task, the original code, and (later) its previous attempt plus *sanitized* feedback with expected outputs stripped out.
3. **Evaluate.** Each candidate must clear, in order, a **correctness gate** (the case `pytest` suite, inside the container) and a **behavior gate** (exact golden-I/O replay for a single function, or differential equivalence at the public API for a multi-file unit). Only candidates that pass **both** are scored — and scoring is a fixed weighted sum of structural metrics with **no LLM anywhere in the scoring path**.
4. **Feedback or stop.** Continue until the structural floor, a generation cap, or a non-improvement plateau.
5. **Return the best, never worse.** Keep the lowest-scoring gate-passing candidate. If nothing beats the baseline, return the **unmodified original**.

> Two readability guards (`suspiciously-simple`, `fragmentation-smell`) **flag** golfed or over-fragmented candidates for human review rather than rejecting them, because there is no objective LLM-free readability oracle and rejecting a genuinely simpler correct answer would violate "objective only."

---

## Install

> **Requirements:** Python ≥ 3.12 (developed on 3.13; the reference host is verified across 3.12–3.14, the sandbox container is pinned to 3.13). **Docker is required** to run any candidate through the gates. Darwin is **not published to PyPI**.

**Reproducible, hash-locked (the supported path for CI, security review, and reproducing results):**

```bash
python3 -m venv .venv
source .venv/bin/activate                          # Windows: .venv\Scripts\activate
pip install --require-hashes -r requirements.txt   # exact, hash-verified closure
```

**Convenience (quick to try, not hash-locked):**

```bash
pip install .   # builds the wheel (hatchling) and installs the six darwin-* console scripts
```

**One-time sandbox image (required to run candidates):**

```bash
docker build -f docker/Dockerfile.sandbox -t darwin-sandbox:py313 docker/
```

**API key (only to *run the loop*, i.e. call the LLM):** set `ANTHROPIC_API_KEY` in your environment or a gitignored `.env`. Read-only checks make no API calls. Running a loop makes live, sub-dollar-per-case Anthropic calls.

> The wheel ships only the `darwin` package (no `cases/`), so an installed CLI has no data on disk — set `DARWIN_DATA_ROOT=/path/to/checkout`. From a source checkout, a walk-up resolver finds `cases/`, `mcases/`, `runs/`, and `reports/` on its own.

---

## Quick start

```bash
# Optimize one single-function case (calls the LLM; needs an API key)
darwin-loop income_tax --cap 5 --plateau 2 --model claude-opus-4-8
#   -> writes a fresh runs/<case>_<UTC>/ with gen_NN.{py,json}, best.py, run.json

# Optimize one multi-file case
darwin-mloop rate_limiter --cap 5 --plateau 2 --model claude-opus-4-8

# Run the full single-function harness, regenerating reports/RESULTS.md
darwin-benchmark
darwin-benchmark --report-only      # re-render the report; NO API calls, no Docker

# Read-only sanity / scoring checks (no API key; Docker required for the gated ones)
python -m darwin.smoke_test         # run each case's reference + original through the gates
python -m darwin.validate_mcase --all   # validate the multi-file store (no Docker, no key)

# Author a new single-function case (LLM-bloats the reference, gates it, freezes metrics)
python -m darwin.build_case seeds/<name>
```

From a source checkout, substitute `python -m darwin.loop` for `darwin-loop`, and so on, and drop `DARWIN_DATA_ROOT`. Full command reference is in [Usage](#usage) below.

---

## Stable surface (the 1.0 compatibility boundary)

Darwin 1.0 commits to a **CLI-and-file-format surface**, not an importable Python API. Depend on these and a future 1.x will not break you:

| Surface | What it covers |
|---|---|
| **Six console scripts** | `darwin-loop`, `darwin-mloop`, `darwin-benchmark`, `darwin-mbenchmark`, `darwin-variance`, `darwin-isolation-audit` (names + documented arguments) |
| **Case directory format** | the on-disk layout of `cases/<id>/` and `mcases/<id>/`, plus the seed inputs (`reference.py`, `test_suite.py`, `spec.json`) documented in [docs/authoring-a-case.md](docs/authoring-a-case.md) |
| **Dataset JSON schema** | the shape of committed result and case artifacts (`reports/v0.9-dataset.json`, `mvariance.json`, `spec.json`, `golden_io.json`, `meta.json`) |

**Internal `darwin.<module>` imports carry NO stability guarantee** — module names and signatures may change within 1.x. Build on the CLIs and file formats, not on importing internals. (A package `__all__` would only govern `from darwin import *`, not `import darwin.<submodule>`, so it cannot express this boundary; the honest expression is this documented contract — [decision 0046](docs/decisions/0046-v1.0-freeze-single-user-trusted-benchmark.md).)

---

## Scope and limitations — read this first

These are not footnotes. They are the most important thing to understand about the project, and stating them plainly is the point.

- **Single-user-trusted, not adversarial-safe.** The container closes the *access* vectors (a candidate cannot touch your host, network, or secrets, and cannot read its own answer key). It does **not** make the behavior gate forgery-proof: the candidate and the trusted result-emitter still share one process *inside* the container, so an adversarial candidate can forge the verdict in-process. This is a **non-issue for single-user optimization** (you have no incentive to forge your own result) and matters **only** if the verdict becomes a third-party-trusted artifact (a public leaderboard, a certification, a multi-tenant service). It is deferred by deliberate decision ([decision 0008](docs/decisions/0008-in-process-verdict-forgery-deferred.md)), not overlooked, and is the headline 2.0 item.
- **A controlled, hand-authored corpus.** Every case starts as a clean reference function I wrote by hand, which a tool then degrades into the bloated input the engine optimizes. This is deliberate: it gives a known-clean target to measure against, so "how close did the engine get" has an exact answer. The trade-off is that the inputs are controlled degradations of authored functions rather than samples of arbitrary real-world code, so the results characterize the engine on this controlled corpus. A population-level claim over real-world code would need a corpus drawn from real-world code.
- **Validation-scale, not a benchmark-grade population.** 30 single-function cases plus 3 multi-file cases establish that the machinery works, not a population-level claim.
- **The multi-file references are soft.** Across 18 multi-file case-runs, all 18 returned a best at or below the reference floor, so "bloat-removed above 100%" measures reference looseness, not candidate excellence. Tightening them is a prerequisite for any benchmark-grade multi-file claim.
- **Multi-file correctness is a strong signal, not proof.** It is differential equivalence at the public API ([decision 0009](docs/decisions/0009-multi-file-equivalence-differential-testing.md)) — strong, but strictly weaker than golden I/O, and sequence- and API-relative.
- **"Simpler" means structurally simpler by a fixed metric** (cyclomatic complexity, logical LOC, nesting, dependencies, dead code). It makes **no** claim about runtime performance or readability.

**What Darwin deliberately is *not*:** not a "self-evolving agent," not emergent self-improvement, and not a forgery-proof judge of adversarial code (it is *access*-safe, not verdict-proof). Those would be overclaims the evidence does not support. The full threat model is in **[SECURITY.md](SECURITY.md)**.

---

## Usage

Two invocation styles, same engine. **Installed** (`pip install .`): the six harnesses are on `PATH`; point them at a data root with `DARWIN_DATA_ROOT=/path/to/checkout`. **From a source checkout**: run modules directly (`python -m darwin.loop`); the walk-up resolver finds the data directories with no flag or env var.

### Single-function (cases under `cases/`)

```bash
darwin-loop sum_evens
darwin-loop income_tax --cap 5 --plateau 2 --model claude-opus-4-8
darwin-benchmark                    # full harness; regenerates reports/RESULTS.md
darwin-benchmark --report-only      # re-render from aggregate.json; no API, no Docker
python -m darwin.smoke_test         # reference + original through the gates
python -m darwin.bakeoff            # compare Layer-3 scoring methods; shows the gaming traps
python -m pytest tests/test_behavior_gate_limits.py -v   # the forgery boundary, as xfail markers
```

### Multi-file (mcases under `mcases/`)

```bash
python -m darwin.validate_mcase --all          # suite, equivalence, catch-test (no Docker, no key)
darwin-mloop rate_limiter --cap 5 --plateau 2 --model claude-opus-4-8
darwin-mbenchmark                              # writes reports/maggregate.json (gitignored)
```

### Authoring a case (no console script — run as modules)

```bash
python -m darwin.build_case seeds/<name>                  # bloat the reference, gate it, freeze metrics
python -m darwin.freeze_metrics cases/<name>/original.py  # structural metrics for one file (no LLM)
```

See **[docs/authoring-a-case.md](docs/authoring-a-case.md)** for the full `spec.json` schema and the reference-authoring rules.

---

## Results in brief

### Single-function

| metric | value |
|---|---|
| cases / runs | 30 cases (7 categories) / 150 runs |
| one-shot (best in gen 1) | **143 / 150 = 95.3%** |
| `best_gen` distribution | gen 1: 143 · gen 2: 4 · gen 3: 3 |
| every run improved over baseline | 150 / 150 |
| feedback loop load-bearing? | **no** |
| total cost | $2.601205 |

The 7 later-generation runs occurred in three cases (`int_to_words`, `parse_version`, `total_price`) across three unrelated categories and are **run-to-run variance near the floor, not function shape**.

### Multi-file (6 runs, not 1 — a single run is one stochastic sample)

| case | best gen (6 runs) | one-shot | `feedback_gain_pp` |
|------|-------------------|:--------:|:------------------:|
| `doc_history` | 1, 2, 2, 1, 2, 2 | 2 / 6 | 0 to 20.47 |
| `rate_limiter` | 2, 2, 2, 2, 1, 2 | 1 / 6 | 0 to 15.11 |
| `task_scheduler` | 1, 2, 2, 2, 1, 3 | 2 / 6 | 0 to 13.14 |

Stable across all six runs: every case improved over baseline every run, zero regressions across all 18 case-runs, and generation 1 alone removes ~87–114.9% of the original-to-floor span. Unstable: the one-shot vs needs-gen-2 split flips run to run, and **none of the 6 runs had all three cases one-shot at once**. Directed feedback is **not reliably load-bearing** here, and not zero either. See [reports/MRESULTS.md](reports/MRESULTS.md) and [decision 0014](docs/decisions/0014-multi-file-feedback-opportunistic-variance.md).

**Reproducing:** single-function logs live under gitignored `runs/` — to verify those numbers, **re-run** the harness. The six multi-file rows are **artifact-backed**: committed snapshots under [reports/variance_runs/](reports/variance_runs/) regenerate `mvariance.json` byte-identically via `python -m darwin.variance_harness derive`, so anyone with the repo reproduces them with no spend ([decision 0035](docs/decisions/0035-artifact-backed-variance-regeneration.md)).

---

## Architecture

```
loop.py  ──calls──▶  generator.py        one LLM candidate (blind to tests/oracle)
   │                      │
   │                      ▼
   └────────────▶  evaluator.py           weighted-sum structural score
                          │                (radon / vulture / ast — no LLM)
                          ▼
                   verify_case.py          Layer 1 pytest gate, then Layer 2 exact
                          │                golden-I/O gate (expected outputs withheld;
                          │                oracle + comparison stay host-side)
                          ▼
                   sandbox_container.py    locked-down Docker container per gate run
                                           (no network, no host FS, mem/CPU/PID caps,
                                           non-root, read-only root, hard timeout)
```

The multi-file loop (`mloop.py`) mirrors the same contract across the same container boundary: `mgenerator.py` rewrites the package (parsed and statically validated, never executed on the host), `mevaluator.py` scores only candidates clearing both the correctness and equivalence gates (`mverify.py`), and the differential-equivalence core `mdiffer.py` is reused by the verifiers. The oracle and the comparison always stay host-side, outside the container.

---

## License

Darwin is licensed under the Apache License 2.0. See [LICENSE](./LICENSE).

---

<p align="center">
  Built by <a href="https://www.nihanthnaiduk.tech/"><b>Nihanth Naidu Kalisetti</b></a>
</p>
