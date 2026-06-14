# Darwin

**A verified Python code simplifier for single-function and multi-file units, with a never-worse-than-baseline guarantee.**

Darwin takes one working-but-bloated Python unit (a single function, or a small
multi-file package) and rewrites it into the simplest version that *still behaves
the same* (exact golden-I/O proof for a single function, strong differential
equivalence at the public API for a multi-file unit), or returns the original
unchanged if it cannot beat it. An LLM proposes rewrites; a deterministic, LLM-free
evaluator decides whether each rewrite is correct, behavior-equivalent, and
structurally simpler. Nothing is accepted on
the model's say-so.

**0.3.0 is the current tagged release.** It stays in the 0.x line on purpose: a 1.0
would signal a stable, production-grade release, and Darwin is not there yet. The
release line, all done and merged:

- **v1, single-function (0.1.0).** The directed generate, evaluate, feedback loop on
  one function, with the never-worse guarantee and the objective evaluator.
- **v2, OS isolation (0.2.0).** Every candidate runs inside a locked-down Docker
  container (no network, no host filesystem, memory/CPU/PID caps, non-root,
  read-only root, all capabilities dropped, hard wall-clock timeout). The container
  is the access-isolation boundary.
- **v3, multi-file.** A multi-file generator, a directed multi-file loop, and a
  multi-file evaluator plus benchmark harness, on top of the single-function engine.
- **v4, CI and Linux portability.** The project's first test-running CI (build the
  sandbox image, run the full suite, gate pushes and pull requests on
  ubuntu-latest), plus a bind-mount staging fix that makes the container run on
  native Linux Docker hosts, not only macOS Docker Desktop.

It is run **from source** and is **not published to PyPI** (see
[pyproject.toml](pyproject.toml)).

> **0.3.0 is an honest early release, not a finished product.** Read
> [Scope and limitations](#scope-and-limitations-read-this-first) before anything
> else. It states plainly what the container closes (untrusted candidate code cannot
> touch your host, network, or secrets), what it still does **not** do (the behavior
> gate is **not** forgery-proof against in-process adversarial code), the small-corpus
> and soft-reference caveats, and the two empirical findings (single-function
> effectively one-shot; multi-file generation 1 does the bulk while directed feedback
> is opportunistic and high-variance).

---

## Scope and limitations (read this first)

These are not footnotes. They are the most important thing to understand about the
project.

- **Single-function and multi-file, both validation-scale.** A single-function case
  is one Python function; a multi-file case (an `mcase`) is a small stateful,
  order-dependent package. Both run end to end through the engine. Neither corpus is
  a benchmark: 5 single-function cases plus 3 multi-file cases (all medium
  difficulty) establish that the machinery works, not a population-level claim. A
  benchmark-grade claim would need a larger, difficulty-spread corpus.
- **Single-function is effectively one-shot.** On the 5-case single-function corpus,
  a capable model reaches the structural complexity floor effectively in
  generation 1: 3 of 5 improved cases returned their best from generation 1, and the
  other 2 reached their best at generation 2 by only a sliver (a fraction of a
  percentage point). The multi-generation directed-feedback loop is *built and
  verified to work*, but it was **not load-bearing** at single-function scope. See
  [reports/RESULTS.md](reports/RESULTS.md).
- **Multi-file: generation 1 does the bulk, feedback is opportunistic.** Over six
  runs of the 3-case multi-file corpus, generation 1 alone removes most of each
  case's bloat every run (roughly 79 to 104 percent of the original-to-floor span),
  but reaching the floor in a single pass is run-dependent. When generation 1 falls
  short, the directed loop opportunistically closes the rest, with high run-to-run
  variance. Directed feedback is therefore **not reliably load-bearing** at this
  scope, and **not zero** either. See [reports/MRESULTS.md](reports/MRESULTS.md),
  [reports/mvariance.json](reports/mvariance.json), and
  [decision 0014](docs/decisions/0014-multi-file-feedback-opportunistic-variance.md).
- **The multi-file references are soft.** Across the 18 multi-file case-runs, 17
  returned a best at or below the reference floor (flagged `suspiciously-simple` or
  `fragmentation-smell`). So bloat-removed above 100 percent measures reference
  looseness, not candidate excellence. Tightening the references is a prerequisite
  for any benchmark-grade multi-file claim.
- **Multi-file correctness is a strong signal, not proof.** Single-function
  correctness is exact golden-I/O replay. Multi-file correctness is differential
  equivalence at the public API
  ([decision 0009](docs/decisions/0009-multi-file-equivalence-differential-testing.md)):
  for the same call sequence, original and candidate must produce identical per-call
  observables on fresh instances. This is strong but not total, strictly weaker than
  golden I/O, and the guarantee is sequence-relative and API-relative. See
  [reports/M0_EQUIVALENCE.md](reports/M0_EQUIVALENCE.md).
- **Access isolation is real; the gate is still NOT forgery-proof.** Every candidate
  runs inside a locked-down Docker container, which closes the demonstrated *access*
  vectors: host, network, and secret access; the golden-oracle read (golden outputs
  never enter the container); the literal `import __main__` driver hijack; and the
  unbounded-output memory risk. What it does **not** close: the candidate and the
  trusted result-emitter still share **one process inside the container**, so an
  adversarial candidate can still forge the gate verdict in-process (the frame-locals
  serializer hijack, pinned as a known-open `xfail`, or compute-and-lie). This is a
  non-issue for single-user optimization (you have no incentive to forge your own
  optimization, and the reward-hack audits found the optimizer never approaches
  forgery); it matters **only** if the gate verdict becomes a third-party-trusted
  artifact (a public leaderboard, a certification, a competitive multi-tenant
  service). Closing it then requires an architecture change (splitting the trusted
  emitter out of the candidate's process), and even that leaves compute-and-lie. This
  is deferred by deliberate decision
  ([decision 0008](docs/decisions/0008-in-process-verdict-forgery-deferred.md)), not
  overlooked. See [SECURITY.md](SECURITY.md).
- **Native Linux is CI-verified, with restraint.** The container previously ran only
  on macOS Docker Desktop; v4 fixed the bind-mount staging so it runs on native Linux
  Docker hosts, and CI exercises the container lockdown probes green on
  ubuntu-latest, so the isolation is no longer macOS-only. This is **one** Linux
  runner, not a multi-distro or kernel-hardening audit, and a formal
  [SECURITY.md](SECURITY.md) writeup of the native-Linux verification is still
  outstanding. Darwin does **not** claim production-grade isolation.
- **"Simpler" means structurally simpler by a fixed metric** (cyclomatic complexity,
  logical LOC, nesting, dependencies, dead code). It makes **no** claim about runtime
  performance, readability, or any property the metric does not measure.

What Darwin deliberately is *not*: it is not a "self-evolving agent," not emergent
self-improvement, and not a forgery-proof judge of adversarial code (it is
*access*-safe, not verdict-proof). Those would be overclaims the evidence does not
support.

---

## What it does

For one case, Darwin runs a directed **generate, evaluate, feedback** loop:

1. **Baseline.** It scores the bloated input (a function's `original.py`, or an
   mcase's `original/` package) as the baseline and keeps it as a guaranteed
   fallback.
2. **Generate.** An LLM proposes one candidate rewrite per generation. The generator
   is **blind to the tests and the oracle**: it sees only the task description, the
   original code, and (on later generations) its previous attempt plus *sanitized*
   feedback with expected outputs stripped out.
3. **Evaluate.** Each candidate must pass, in order:
   - a **correctness gate**, the case `pytest` suite passing inside the container;
     then
   - a behavior gate. Single-function: exact **golden-I/O** replay (expected outputs
     are withheld from the container, so the candidate cannot read its own answer
     key). Multi-file: **differential equivalence** at the public API against the
     original.

   Only candidates that clear **both** gates are scored. Scoring is a fixed weighted
   sum of **structural** metrics (via `radon`, `vulture`, and `ast`). **No LLM judges
   code quality** anywhere in the scoring path.
4. **Feedback or stop.** The loop continues until it hits the structural floor, a
   generation cap, or a non-improvement plateau.
5. **Return the best, never worse.** It keeps the lowest-scoring gate-passing
   candidate found. If nothing scores strictly below the baseline, it returns the
   **unmodified original**. The result is therefore never *worse-scoring* than the
   input (by the structural metric).

Two readability guards (`suspiciously-simple`, `fragmentation-smell`) **flag** golfed
or over-fragmented candidates for human review rather than rejecting them, because
there is no objective, LLM-free readability oracle and rejecting a genuinely simpler
correct answer would violate "objective only."

---

## Install

Darwin is run **from source** (it is not pip-installable yet; see
[pyproject.toml](pyproject.toml)).

Requirements: **Python >= 3.10** (developed on **3.13**; the host that replays the
reference is verified across **Python 3.12 to 3.14**, with canonical equivalence
outcomes byte-identical for all three multi-file cases, while the sandbox container
stays pinned to **3.13**).

```bash
# from the repository root
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt     # radon, vulture, pytest, anthropic (all pinned)
```

**Docker is a prerequisite.** Candidate code executes inside a container, so anything
that runs a candidate through the gates needs Docker installed and running, and the
sandbox image built once:

```bash
# one-time host setup, from the repository root
docker build -f tools/Dockerfile.sandbox -t darwin-sandbox:py313 tools/
```

CI builds this same image and exercises the container lockdown probes green on
ubuntu-latest, so the container runs on native Linux Docker hosts as well as macOS
Docker Desktop. The native-Linux verification is one CI runner, not a multi-distro or
kernel-hardening audit, and the formal native-Linux writeup in
[SECURITY.md](SECURITY.md) is still outstanding (it currently carries the pre-CI
Docker-Desktop-only caveat).

**API key (only needed to *run the loop*, that is, to call the LLM).** Set
`ANTHROPIC_API_KEY` in your environment, or put it in a `.env` file at the repository
root:

```bash
# .env  (already gitignored, never commit it)
ANTHROPIC_API_KEY=sk-ant-...
```

Running a loop makes live Anthropic API calls and incurs real (sub-dollar per case)
token cost. The read-only checks (`smoke_test.py`, `validate_mcase.py`, the
behavior-gate limits test) make **no** API calls and need no key. Of those,
`validate_mcase.py` needs neither Docker nor a key; the others run candidates through
the container and so require Docker. `benchmark.py --report-only` and
`freeze_metrics.py` need neither Docker nor a key.

---

## Usage

The tools are flat scripts with bare imports, so **run them from the `tools/`
directory** using the virtualenv's Python (it has `radon` and `vulture`).

### Single-function (cases under `cases/`)

```bash
cd tools

# Optimize one case (calls the LLM; needs an API key). Cases live in ../cases/.
python loop.py sum_evens
python loop.py income_tax --cap 5 --plateau 2 --model claude-opus-4-8
#   -> writes a fresh ../runs/<case>_<UTC>/ with gen_NN.{py,json}, best.py, run.json

# Run the full single-function validation harness over every case in ../cases/
# (calls the LLM; every gate run executes inside the container), regenerating
# ../reports/aggregate.json and ../reports/RESULTS.md.
python benchmark.py

# Re-render the report from an existing aggregate.json. NO API calls, no Docker.
python benchmark.py --report-only

# Read-only sanity / scoring checks (no API key, but Docker required, since they
# run candidates through the container gates):
python smoke_test.py     # runs each case's reference + original through the gates
python bakeoff.py        # compares Layer-3 scoring methods; shows the gaming traps

# Documents the behavior-gate forgery boundary as an executable, expected-fail
# regression marker (Docker required; the gate runs in the container). The two
# in-process forgery vectors are pinned as xfail (decision 0008, SECURITY.md).
python -m pytest test_behavior_gate_limits.py -v
```

### Multi-file (mcases under `mcases/`)

```bash
cd tools

# Validate the multi-file case store: suite, self-equivalence, reference-equivalence,
# and the catch-test (an mcase is sound only if its corpus catches every planted
# break). No Docker, no API key, no LLM.
python validate_mcase.py --all
python validate_mcase.py rate_limiter

# Optimize one multi-file case (calls the LLM; needs an API key; runs in the
# container). Cases live in ../mcases/ (doc_history, rate_limiter, task_scheduler).
python mloop.py rate_limiter --cap 5 --plateau 2 --model claude-opus-4-8

# Run the multi-file validation harness over the mcases. Writes the machine-readable
# ../reports/maggregate.json (gitignored) and prints a per-case table; the narrative
# ../reports/MRESULTS.md is authored separately, not auto-generated by this command.
python mbenchmark.py
```

Authoring a new single-function case (clean reference, bloated original, frozen
baseline):

```bash
cd tools
python build_case.py ../seeds/<name>          # LLM-bloats the reference, gates it, freezes metrics
python freeze_metrics.py ../cases/<name>/original.py   # structural metrics for one file (no LLM)
```

---

## Results

Present both findings honestly. They are different.

### Single-function (v1)

Summarized in **[reports/RESULTS.md](reports/RESULTS.md)** (machine-readable:
[reports/aggregate.json](reports/aggregate.json)). Headline numbers from that run
(`claude-opus-4-8`, `cap=5`, `plateau=2`, every gate run inside the container):

| metric | value |
|---|---|
| cases improved over baseline | **5 / 5** |
| baseline returned (nothing beat it) | 0 / 5 |
| improved cases that were one-shot (best from generation 1) | **3 / 5** |
| cases that reached their best at generation 2+ | 2 / 5 (marginal: `format_duration` +0.37 pp, `int_to_words` +0.4 pp) |
| feedback loop load-bearing on this corpus? | **no** |
| total cost (real API token counts) | $0.16912 |

A capable model reaches the structural floor effectively one-shot here. The two
generation-2 bests added only a fraction of a percentage point on top of what
generation 1 had already removed (99.6 percent and 99.2 percent of the bloat
respectively), so directed feedback did real but marginal work on 2 cases and none on
the other 3. The feedback loop's verified value at this scope is the gates,
best-of-N retention, and the never-worse-than-baseline guarantee, not multi-generation
improvement.

### Multi-file (v3)

Summarized in **[reports/MRESULTS.md](reports/MRESULTS.md)** and the six-run variance
dataset **[reports/mvariance.json](reports/mvariance.json)**; the finding is recorded
as
[decision 0014](docs/decisions/0014-multi-file-feedback-opportunistic-variance.md).
**This rests on six runs, not one**, because a single live run is one stochastic
sample: early single runs landed both "all three one-shot" and "all three needed
generation 2," which would have supported opposite headlines.

| case | best generation (6 runs) | one-shot | `feedback_gain_pp` range |
|------|--------------------------|:--------:|:------------------------:|
| `doc_history` | 1, 2, 2, 1, 2, 1 | 3 / 6 | 0 to 24.02 |
| `rate_limiter` | 1, 2, 3, 2, 2, 3 | 1 / 6 | 0 to 22.48 |
| `task_scheduler` | 1, 2, 2, 2, 1, 2 | 2 / 6 | 0 to 10.81 |

Stable across all six runs: every run improved all three cases over baseline; the
baseline original was never returned; zero regressions across all 18 case-runs;
generation 1 alone removes roughly 79 to 104 percent of the original-to-floor span on
every case, every run; and 17 of 18 case-runs returned a best at or below the
reference floor. Unstable: the one-shot versus needs-generation-2-or-more split flips
run to run, and **only 1 of the 6 runs had all three cases one-shot at once**;
`feedback_gain_pp` ranges from 0 to about 24 percentage points for the same case
across runs.

Two honesty notes carried straight from the report. First, the references are soft:
because 17 of 18 bests sit at or below the floor (the one exception, `task_scheduler`
run 1, landed at 98.2 percent of its span, about 1.8 percent above the floor),
**bloat-removed above 100 percent reflects reference looseness, not candidate
excellence**, and the `feedback_gain_pp` magnitudes are upper bounds. Second, this is
**3 medium-difficulty cases over six runs, a directional validation result, not a
benchmark**.

### Provenance

The per-generation candidate logs that back these numbers live in `runs/` (and the
multi-file aggregate in `maggregate.json`), which are **gitignored**. The committed
`reports/` are derived summaries; to verify independently, **re-run** the harness
rather than trusting committed logs. The six multi-file variance rows are
hand-recorded from the printed `mbenchmark.py` output; only the most recent run is
independently corroborable from the gitignored on-disk aggregate. Retaining per-run
snapshots or a fixed regeneration seed (so all six are reproducible if challenged) is
a recorded follow-up item.

---

## Continuous integration

The project has a GitHub Actions workflow,
[.github/workflows/ci.yml](.github/workflows/ci.yml), that builds the sandbox image
and runs the full test suite on `ubuntu-latest`, gating pushes (so a phase branch can
be seen green before merge) and pull requests to `main`. The expected result is
**75 passed, 2 xfailed**. The two `xfailed` are the decision-0008 in-process
forgery vectors in `tools/test_behavior_gate_limits.py`, pinned known-open; pytest's
default exit codes fail CI on any failure or on an unexpected pass (an `xfail` that
turns `XPASS` is the signal that a forgery vector was closed and the marker must be
updated). The suite uses fakes and the container and never a live
`ANTHROPIC_API_KEY`, so CI needs no secrets.

CI also exercises the container lockdown probes (the `mverify` probes that confirm the
candidate cannot see the original or the recorded outcomes from inside the container)
green on `ubuntu-latest`, which is what establishes that the isolation is no longer
macOS-only. It remains one Linux runner, not a multi-distro or kernel-hardening audit.

---

## Architecture

```
Single-function (v1 + v2 isolation):

seeds/        Hand-written case sources: spec.json + clean reference.py + test_suite.py
   │  build_case.py  (bloat.py LLM-bloats the reference, gates it, freezes metrics)
   ▼
cases/        Materialized cases. Each: original.py (bloated input), reference.py
              (clean floor), test_suite.py (correctness gate), golden_io.json
              (behavior gate I/O), baseline_metrics.json, meta.json
```

```
Multi-file (v3):

mcases/       Multi-file cases. Each: original/ (bloated package), reference/ (clean
              floor), corpus.py (build_corpus() -> call sequences), test_suite.py,
              breaks.py (planted breaks for the catch-test), conventions.md,
              baseline_metrics.json, meta.json
```

The single-function loop, per generation:

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

The multi-file loop (`mloop.py`) mirrors the single-function contract across the same
container boundary: `mgenerator.py` rewrites the bloated package (parsed and
statically validated from the model output, never executed on the host),
`mevaluator.py` scores only candidates that clear both the correctness gate and the
equivalence gate (`mverify.py`, which runs the untrusted candidate across the
container boundary while the original replays host-side), and `mcase_metrics.py`
aggregates the structural metric basket for Layer 3. The differential equivalence core
`mdiffer.py` is reused, not reimplemented, by the verifiers.

- **`loop.py` / `mloop.py`** - orchestrators: baseline, generation cap, plateau rule,
  never-worse fallback, sanitized feedback, per-generation logging.
- **`generator.py` / `mgenerator.py`** - single Anthropic API call; extract and
  validate one candidate (the multi-file generator never executes the candidate on
  the host).
- **`evaluator.py` / `mevaluator.py`** - objective structural scoring (fixed weights;
  `maintainability_index` is measured but weight-0 because it is cosmetically
  gameable; guards flag, never reject).
- **`verify_case.py` / `mverify.py` / `sandbox_container.py`** - the gates and the
  locked-down-container sandbox primitive. The oracle and the comparison stay
  host-side, outside the container.
- **`benchmark.py` / `mbenchmark.py`** - run the loop over the corpus from each run's
  own logs (no re-measurement). `benchmark.py` writes the committed single-function
  summary (`reports/aggregate.json` and `reports/RESULTS.md`); `mbenchmark.py` writes
  only the machine-readable `reports/maggregate.json` (gitignored) and prints the
  per-case table, with `reports/MRESULTS.md` authored separately.

The v1 in-process `sandbox.py` primitive is retained in the tree; the gates route
through `sandbox_container.py`, which exposes the same contract across an OS boundary.

---

## Security / threat model

Candidate code runs in a locked-down container and cannot touch your host, network,
or secrets. That closes the demonstrated access-based forgery vectors (the
golden-oracle read and the literal `import __main__` driver hijack) plus the
unbounded-output memory risk. It does **not** make the behavior gate forgery-proof:
the candidate still shares one process with the trusted result-emitter *inside* the
container, so an adversarial candidate can still forge the verdict in-process (the
known-open frame-locals hijack, or compute-and-lie). That residual matters **only**
when the verdict becomes a third-party-trusted artifact (leaderboard, certification,
multi-tenant service); for single-user optimization it is a non-issue, and it is
deferred by deliberate decision
([decision 0008](docs/decisions/0008-in-process-verdict-forgery-deferred.md)). The
isolation now runs and holds on native Linux in CI as well as macOS Docker Desktop,
but that is one Linux runner, not a multi-distro or kernel-hardening audit, and the
formal native-Linux writeup is still outstanding. The full model (what the container
closes, the open in-process residual and its trigger condition, and optional future
hardening) is in **[SECURITY.md](SECURITY.md)**, which still carries the pre-CI
Docker-Desktop-only native-Linux caveat pending that writeup.

---

## Roadmap

Only genuinely remaining work (v1 through v4 are done and merged):

- **Split the trusted emitter out of the candidate's process** to close the
  in-process verdict-forgery residual, required *only* if the gate verdict becomes a
  third-party-trusted artifact (and even then compute-and-lie remains).
- **A formal native-Linux security writeup** in SECURITY.md. CI verifies the lockdown
  on one ubuntu-latest runner; a multi-distro and kernel-hardening audit is
  outstanding before any production deployment with untrusted users.
- **Tighter multi-file references and a real benchmark.** The references are soft
  (most bests sit at or below the floor), and the corpus is small (5 single-function
  plus 3 multi-file cases). Tightening the references and growing the corpus across
  categories and difficulties is the prerequisite for any benchmark-grade claim.
- **A robustness fix to `_require_image`** (the sandbox-image preflight in
  `tools/sandbox_container.py`): it treats any non-zero `docker image inspect` as
  image-absent, so a transient daemon error reads as a missing image rather than a
  daemon problem.
- **Variance-data reproducibility.** Retain per-run snapshots or a fixed regeneration
  seed so all six multi-file variance rows are regenerable from a retained artifact,
  not just the most recent run.
- **Optional defense-in-depth** (a custom seccomp profile, a user-namespace remap).
  Not required for the current threat model; noted as possible future hardening only.

---

## License

Darwin is licensed under the Apache License 2.0. See [LICENSE](./LICENSE).
