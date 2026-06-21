# Darwin

**A research engine and reproducible benchmark for studying LLM-driven Python code
simplification, single-user-trusted.** Inside that frame, Darwin is a verified code
simplifier for single-function and multi-file units, with a never-worse-than-baseline
guarantee.

Darwin takes one working-but-bloated Python unit (a single function, or a small
multi-file package) and rewrites it into the simplest version that *still behaves
the same* (exact golden-I/O proof for a single function, strong differential
equivalence at the public API for a multi-file unit), or returns the original
unchanged if it cannot beat it. An LLM proposes rewrites; a deterministic, LLM-free
evaluator decides whether each rewrite is correct, behavior-equivalent, and
structurally simpler. Nothing is accepted on the model's say-so.

Darwin is built to study and reproduce that behavior on a controlled corpus, **not** to
run on untrusted code and trust the verdict. It is **single-user-trusted**: it does
**not** defend against adversarial code, and its in-process verdict-forgery boundary is
open by design ([decision 0008](docs/decisions/0008-in-process-verdict-forgery-deferred.md),
deferred to 2.0), so **its verdicts are not to be trusted on untrusted code**.

**1.0.0 is the current version** — the v1.0 freeze. 1.0 marks Darwin as a stable,
reproducible **single-user-trusted** research benchmark and engine, with a committed
[stable surface](#stable-surface-the-10-compatibility-boundary). It does **not** mean
production-grade against adversarial code: the in-process verdict-forgery boundary stays
**open by design** and is deferred to 2.0
([decision 0008](docs/decisions/0008-in-process-verdict-forgery-deferred.md)), and the
synthetic-corpus, small-corpus, and soft-reference limitations below stand. The 0.x-to-1.0
reframing (1.0 commits to a reproducible single-user-trusted benchmark, not to closing the
forgery boundary that decision 0005 originally reserved 1.0 for) is recorded in
[decision 0046](docs/decisions/0046-v1.0-freeze-single-user-trusted-benchmark.md). The
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
- **v0.5, correctness, determinism, and reproducibility (0.5.0).** A documented
  feedback-materiality threshold (with the aggregate regenerated to match the prose),
  an explicit pinned temperature with full run provenance recorded in run.json, a
  variance harness with committed-snapshot persistence, uuid-minted dynamic-import
  names across the evaluator loaders, and the oracle witness prefixes bound to a
  shared marker guarded by a real-producer leak test. The artifact-backed multi-file
  variance regeneration is deferred to an authorized run.
- **v0.6, supply-chain and isolation hardening (0.6.0).** The sandbox base image
  pinned by manifest-list digest with a documented rotation procedure; hash-locked
  lockfiles (pip-tools, `--generate-hashes`) for the host, CI, and the sandbox image
  installed with `--require-hashes`, plus a CycloneDX SBOM build artifact and an
  advisory pip-audit vulnerability scan in CI; a CI matrix exercising the container
  lockdown probe across two Ubuntu runners on cgroup v2, recording the actual cgroup
  version, with a native-Linux section in SECURITY.md scoped to the verified evidence;
  and defense-in-depth: opt-in, off-by-default seccomp plumbing with a byte-identical
  default argv and an example starting-point profile, plus a typed VerdictEmitter seam
  (in-process default, serializable verdict) prepared for the 2.0 out-of-process
  emitter. In-process verdict forgery stays open by design at 1.0 (decision 0008).
- **v0.7, test and CI maturity (0.7.0).** The pytest 8.3.5 to 9.0.3 bump that clears
  CVE-2025-71176 (re-locked on Python 3.13, adding `pygments` as a new transitive of
  the runtime and sandbox closures); direct unit tests for the loop orchestrator and
  the single-function verifier (`loop.py` and `verify_case.py`, both at 99 percent line
  coverage); the four quality gates (ruff lint and format, mypy, gitleaks) plus the
  pip-audit dependency scan driven to zero and flipped from advisory to blocking, with
  a `--cov-fail-under=56` coverage floor (production coverage measured 58 percent, less
  a 2-point margin); and a Python 3.12/3.13/3.14 host CI matrix on the single hashed
  lock, backing the documented 3.12-to-3.14 host range. No change to the optimization,
  scoring, or equivalence behavior.
- **v0.8, packaging (0.8.0).** The flat `tools/` scripts became an importable `darwin`
  package under `src/` (absolute imports, a `paths.py` walk-up data-root resolver), with
  a hatchling build-system and six `darwin-*` console scripts, so `pip install .` now
  works. Data-root resolution was deferred out of import time (a PEP 562 lazy-attribute
  pattern) after the packaging audit found import-time filesystem work broke the
  installed CLIs. The coverage floor was re-based to the package-scoped number
  (`--cov-fail-under=62`, from ~64.6 percent production coverage). No change to the
  optimization, scoring, or equivalence behavior.
- **v0.9, corpus expansion (0.9.0).** The single-function corpus grew from the retired
  5-case validation set to a 30-case synthetic corpus across seven degradation
  categories (a seventh, `defensive_overengineering`, added by Amendment 1), each case
  run 5 times under one frozen config (run-and-record only; no engine, scoring, gate, or
  `build_case` change). The run produced the authoritative one-shot finding: 143 of 150
  runs (95.3 percent) reached the returned-best candidate in generation 1, superseding
  the 5-case validation that could only suggest it; the loop's role is run-to-run
  near-floor variance, not function shape. A corpus-wide temporal-freeze proof (every
  case frozen before it was run; the committed `original.py` byte-identical to the scored
  input in all 150 runs) backs the run. No change to the optimization, scoring, or
  equivalence behavior.
- **v1.0, the freeze (1.0.0).** Results reconciled to the v0.9 evidence, the
  single-user-trusted trust posture and threat model finalized, the benchmark made
  externally extendable (a documented case-authoring schema,
  [docs/authoring-a-case.md](docs/authoring-a-case.md)), and the
  [stable 1.0 surface](#stable-surface-the-10-compatibility-boundary) declared (the six
  console scripts, the case directory format, and the dataset JSON schema; internal
  modules carry no import-stability guarantee). Explicitly **not** a capability change and
  **not** a closing of the in-process forgery boundary, which stays open by design and
  deferred to 2.0 (decision 0046).

It can be installed from a local checkout (`pip install .`) or run straight from the
source tree, and is **not published to PyPI** (see [pyproject.toml](pyproject.toml)).

> **1.0.0 is an honest, reproducible benchmark release under a single-user-trusted
> posture, not a production-grade-against-adversarial-code product.** Read
> [Scope and limitations](#scope-and-limitations-read-this-first) before anything
> else. It states plainly what the container closes (untrusted candidate code cannot
> touch your host, network, or secrets), what it still does **not** do (the behavior
> gate is **not** forgery-proof against in-process adversarial code), the
> synthetic-corpus, small-corpus, and soft-reference caveats, and the two empirical
> findings (single-function effectively one-shot; multi-file generation 1 does the bulk
> while directed feedback is opportunistic and high-variance).

---

## Scope and limitations (read this first)

These are not footnotes. They are the most important thing to understand about the
project.

- **Single-function and multi-file, both validation-scale.** A single-function case
  is one Python function; a multi-file case (an `mcase`) is a small stateful,
  order-dependent package. Both run end to end through the engine. Neither corpus is
  a benchmark: 30 single-function cases (seven degradation categories, difficulties
  easy/medium/hard) plus 3 multi-file cases (all medium difficulty) establish that the
  machinery works, not a population-level claim. A benchmark-grade claim would need a
  larger, real-world corpus.
- **The corpus is synthetic (the headline limitation).** Every single-function case is
  a hand-authored clean reference degraded by the bloat tool, not real-world code, so
  the result characterizes the engine's behavior on *controlled degradations* of
  authored functions, not real-world optimization. Both ends of the measured span are
  synthetic: the bloated original is tool-generated and the reference floor is
  hand-authored. A real-world-grade claim needs a corpus drawn from real-world code,
  which this is not. See [reports/RESULTS.md](reports/RESULTS.md).
- **Single-function is effectively one-shot.** On the 30-case single-function corpus
  run 5 times each (150 runs), a capable model reaches the structural complexity floor
  effectively in generation 1: 143 of 150 runs (95.3 percent) returned their best from
  generation 1. The 7 runs (4.7 percent) that returned a later generation's candidate
  are run-to-run stochastic recovery near the floor, spread across three unrelated
  categories, **not** a property of function shape. The multi-generation
  directed-feedback loop is *built and verified to work*, but it was **not
  load-bearing** at single-function scope. See [reports/RESULTS.md](reports/RESULTS.md).
- **Multi-file: generation 1 does the bulk, feedback is opportunistic.** Over six
  runs of the 3-case multi-file corpus, generation 1 alone removes most of each
  case's bloat every run (roughly 87 to 114.9 percent of the original-to-floor span),
  but reaching the floor in a single pass is run-dependent. When generation 1 falls
  short, the directed loop opportunistically closes the rest, with high run-to-run
  variance. Directed feedback is therefore **not reliably load-bearing** at this
  scope, and **not zero** either. See [reports/MRESULTS.md](reports/MRESULTS.md),
  [reports/mvariance.json](reports/mvariance.json), and
  [decision 0014](docs/decisions/0014-multi-file-feedback-opportunistic-variance.md).
- **The multi-file references are soft.** Across the 18 multi-file case-runs, all 18
  returned a best at or below the reference floor; 14 of the 18 carried a below-floor
  flag (`suspiciously-simple` or `fragmentation-smell`). So bloat-removed above 100
  percent measures reference looseness, not candidate excellence. Tightening the
  references is a prerequisite for any benchmark-grade multi-file claim.
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
  Docker hosts, and CI now runs the container lockdown probe green on a native-Linux
  matrix (`ubuntu-22.04` and `ubuntu-24.04`, both cgroup v2), so the isolation is no
  longer macOS-only. The formal native-Linux writeup is **done**: it is the native-Linux
  section of [SECURITY.md](SECURITY.md)
  ([decision 0030](docs/decisions/0030-native-linux-lockdown-verification-ci.md)). What
  remains genuinely open is **cgroup v1, non-Ubuntu distributions, and a kernel-hardening
  audit**, none of which this matrix exercises (a documented self-hosted follow-up).
  Darwin does **not** claim production-grade isolation.
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

There are two install paths. Requirements either way: **Python >= 3.12** (developed on
**3.13**; the host that replays the reference is verified across **Python 3.12 to
3.14**, with canonical equivalence outcomes byte-identical for all three multi-file
cases, while the sandbox container stays pinned to **3.13**). Darwin is **not published
to PyPI** either way.

**1. Reproducible, supported install (hash-locked).** This is the supported path for
CI, security review, and reproducing results. It pins the exact dependency closure and
verifies every artifact by hash:

```bash
# from the repository root
python3 -m venv .venv
source .venv/bin/activate                          # Windows: .venv\Scripts\activate
pip install --require-hashes -r requirements.txt   # exact, hash-verified closure
```

`requirements.txt` is generated by pip-tools with `--generate-hashes` and installed
with `--require-hashes`, so a substituted or tampered package fails the install
([decision 0028](docs/decisions/0028-hash-locked-dependency-lockfiles.md)). Run Darwin
straight from the checkout: the modules live under `src/darwin/`, and a `paths.py`
walk-up resolver finds the `cases/`, `mcases/`, `runs/`, and `reports/` data
directories at the checkout root on its own.

**2. Convenience install (`pip install .`, NOT hash-locked).** As of 0.8 the package
builds and installs:

```bash
# from the repository root
pip install .          # builds the wheel (hatchling) and installs the darwin package
```

This puts six console scripts on `PATH` (`darwin-loop`, `darwin-mloop`,
`darwin-benchmark`, `darwin-mbenchmark`, `darwin-variance`, `darwin-isolation-audit`).
It resolves `[project].dependencies` as **version ranges from PyPI, not the hash-locked
closure**, so it is the quick path for trying Darwin, **not** the reproducible or
security-reviewed one. For that, use the hash-locked install above. The wheel ships
**only** the `darwin` package (no `cases/`, `mcases/`, or `docker/`), so an installed
CLI has no data on disk: set `DARWIN_DATA_ROOT` to the data root (the checkout root) to
run it. The per-command directory flags (`--cases-dir` / `--mcases-dir` / `--out`) override
only their own lookup and do not on their own satisfy an installed run, which also resolves
`runs/` (and `reports/`) under the data root (see [Usage](#usage)).

**Docker is a prerequisite.** Candidate code executes inside a container, so anything
that runs a candidate through the gates needs Docker installed and running, and the
sandbox image built once:

```bash
# one-time host setup, from the repository root
docker build -f docker/Dockerfile.sandbox -t darwin-sandbox:py313 docker/
```

CI builds this same image, and the container lockdown probe runs green on a native-Linux
matrix (`ubuntu-22.04` and `ubuntu-24.04`, both cgroup v2) in
[.github/workflows/isolation.yml](.github/workflows/isolation.yml), so the container runs
on native Linux Docker hosts as well as macOS Docker Desktop. The native-Linux writeup is
done (the native-Linux section of [SECURITY.md](SECURITY.md), decision 0030); cgroup v1,
non-Ubuntu distributions, and kernel hardening are not exercised and remain a documented
self-hosted follow-up.

**API key (only needed to *run the loop*, that is, to call the LLM).** Set
`ANTHROPIC_API_KEY` in your environment, or put it in a `.env` file at the repository
root:

```bash
# .env  (already gitignored, never commit it)
ANTHROPIC_API_KEY=sk-ant-...
```

Running a loop makes live Anthropic API calls and incurs real (sub-dollar per case)
token cost. The read-only checks (`python -m darwin.smoke_test`,
`python -m darwin.validate_mcase`, the behavior-gate limits test) make **no** API calls
and need no key. Of those, `python -m darwin.validate_mcase` needs neither Docker nor a
key; the others run candidates through the container and so require Docker.
`darwin-benchmark --report-only` and `python -m darwin.freeze_metrics` need neither
Docker nor a key.

---

## Usage

Two invocation styles, same engine:

- **Installed** (`pip install .`): the six harnesses are on `PATH` as `darwin-loop`,
  `darwin-mloop`, `darwin-benchmark`, `darwin-mbenchmark`, `darwin-variance`, and
  `darwin-isolation-audit`. An installed CLI has no data on disk, so point it at a data
  root with `DARWIN_DATA_ROOT=/path/to/checkout`. The per-command directory flags
  (`--cases-dir`, `--mcases-dir`, `--out`) override only their own lookup (a checkout-side
  convenience) and do not on their own satisfy an installed run, which also resolves
  `runs/` (and `reports/`) under the data root. The authoring/diagnostic tools without a
  console script run as `python -m darwin.<name>`.
- **From a source checkout**: run the modules directly, e.g. `python -m darwin.loop`.
  The `paths.py` walk-up resolver finds `cases/`, `mcases/`, `runs/`, and `reports/` at
  the checkout root, so no data flag or env var is needed.

The examples below use the installed console-script names; from a checkout, substitute
`python -m darwin.loop` for `darwin-loop`, and so on (and drop the `DARWIN_DATA_ROOT`).

### Single-function (cases under `cases/`)

```bash
# Optimize one case (calls the LLM; needs an API key).
darwin-loop sum_evens
darwin-loop income_tax --cap 5 --plateau 2 --model claude-opus-4-8
#   -> writes a fresh runs/<case>_<UTC>/ with gen_NN.{py,json}, best.py, run.json

# Run the full single-function validation harness over every case in cases/ (calls the
# LLM; every gate run executes inside the container), regenerating reports/aggregate.json
# and reports/RESULTS.md.
darwin-benchmark

# Re-render the report from an existing aggregate.json. NO API calls, no Docker.
darwin-benchmark --report-only

# Read-only sanity / scoring checks (no API key, but Docker required, since they run
# candidates through the container gates):
python -m darwin.smoke_test     # runs each case's reference + original through the gates
python -m darwin.bakeoff        # compares Layer-3 scoring methods; shows the gaming traps

# Documents the behavior-gate forgery boundary as an executable, expected-fail
# regression marker (Docker required; the gate runs in the container). The two
# in-process forgery vectors are pinned as xfail (decision 0008, SECURITY.md).
python -m pytest tests/test_behavior_gate_limits.py -v
```

### Multi-file (mcases under `mcases/`)

```bash
# Validate the multi-file case store: suite, self-equivalence, reference-equivalence,
# and the catch-test (an mcase is sound only if its corpus catches every planted
# break). No Docker, no API key, no LLM.
python -m darwin.validate_mcase --all
python -m darwin.validate_mcase rate_limiter

# Optimize one multi-file case (calls the LLM; needs an API key; runs in the
# container). Cases live in mcases/ (doc_history, rate_limiter, task_scheduler).
darwin-mloop rate_limiter --cap 5 --plateau 2 --model claude-opus-4-8

# Run the multi-file validation harness over the mcases. Writes the machine-readable
# reports/maggregate.json (gitignored) and prints a per-case table; the narrative
# reports/MRESULTS.md is authored separately, not auto-generated by this command.
darwin-mbenchmark
```

Authoring a new single-function case (clean reference, bloated original, frozen
baseline). These two have no console script, so run them as modules:

```bash
python -m darwin.build_case seeds/<name>               # LLM-bloats the reference, gates it, freezes metrics
python -m darwin.freeze_metrics cases/<name>/original.py   # structural metrics for one file (no LLM)
```

When running these from an installed package **outside a checkout**, set
`DARWIN_DATA_ROOT=/path/to/checkout` so the resolver can find the data directories. Both
harnesses run as `python -m darwin.<name>` and take no `--cases-dir` / `--mcases-dir` /
`--out` flag; those per-lookup flags override only their own directory and do not on
their own satisfy an installed run (which also resolves `runs/` and `reports/`). From a
checkout, the walk-up resolver handles it.

---

## Results

Present both findings honestly. They are different.

### Single-function (v1)

Summarized in **[reports/RESULTS.md](reports/RESULTS.md)** (machine-readable:
[reports/v0.9-dataset.json](reports/v0.9-dataset.json)). The authoritative 30-case run
(`claude-opus-4-8`, `cap=5`, `plateau=2`, every gate run inside the container), 30 cases
across 7 degradation categories run 5 times each:

| metric | value |
|---|---|
| single-function cases / total runs | 30 cases (7 categories) / 150 runs |
| runs that reached the returned best in generation 1 (one-shot) | **143 / 150 = 95.3 percent** |
| `best_gen` distribution across 150 runs | gen 1: 143, gen 2: 4, gen 3: 3 |
| runs that returned a best first found in generation 2 or 3 | 7 / 150 (4.7 percent) |
| every run improved over baseline; baseline original never returned | 150 / 150 |
| feedback loop load-bearing on this corpus? | **no** |
| total cost (real API token counts) | $2.601205 |

A capable model reaches the structural floor effectively one-shot here: 143 of 150 runs
returned their best from generation 1. The 7 runs (4.7 percent) that returned a later
generation's candidate occurred in three cases (`int_to_words`, `parse_version`,
`total_price`) and are **run-to-run stochastic recovery near the floor, not a property
of function shape or category**: the same case is one-shot on some runs and
loop-recovered on others, and the three cases span three unrelated categories. The loop
therefore functions as occasional insurance against a generation-1 miss, not a
structural requirement; its verified value at this scope is the gates, best-of-N
retention, and the never-worse-than-baseline guarantee, not multi-generation
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
| `doc_history` | 1, 2, 2, 1, 2, 2 | 2 / 6 | 0 to 20.47 |
| `rate_limiter` | 2, 2, 2, 2, 1, 2 | 1 / 6 | 0 to 15.11 |
| `task_scheduler` | 1, 2, 2, 2, 1, 3 | 2 / 6 | 0 to 13.14 |

Stable across all six runs: every run improved all three cases over baseline; the
baseline original was never returned; zero regressions across all 18 case-runs;
generation 1 alone removes roughly 87 to 114.9 percent of the original-to-floor span on
every case, every run; and all 18 of 18 case-runs returned a best at or below the
reference floor. Unstable: the one-shot versus needs-generation-2-or-more split flips
run to run, and **none of the 6 runs had all three cases one-shot at once**;
`feedback_gain_pp` ranges from 0 to about 20 percentage points for the same case
across runs.

Two honesty notes carried straight from the report. First, the references are soft:
because all 18 of 18 bests sit at or below the floor (this regeneration had no
above-floor exception, unlike the 2026-06-13 dataset whose single `task_scheduler`
exception did not recur), **bloat-removed above 100 percent reflects reference
looseness, not candidate excellence**, and the `feedback_gain_pp` magnitudes are upper
bounds. Second, this is **3 medium-difficulty cases over six runs, a directional
validation result, not a benchmark**.

### Provenance

The per-generation candidate logs that back these numbers live in `runs/` (and the
single-function aggregate inputs), which are **gitignored**; to verify the
single-function numbers independently, **re-run** the harness rather than trusting the
gitignored logs. The six multi-file variance rows are **artifact-backed**: each run wrote
its `maggregate.json` into a committed snapshot under
[reports/variance_runs/](reports/variance_runs/) (`run_00` through `run_05`), and
`reports/mvariance.json` and `reports/MRESULTS.md` are regenerated from those committed
snapshots by `python -m darwin.variance_harness derive`, which is **byte-identical** on
re-derive, so anyone with the repo can reproduce all six rows with no spend
([decision 0035](docs/decisions/0035-artifact-backed-variance-regeneration.md)).

---

## Continuous integration

The project has a GitHub Actions workflow,
[.github/workflows/ci.yml](.github/workflows/ci.yml), that builds the sandbox image
and runs the full test suite on `ubuntu-latest`, gating pushes (so a phase branch can
be seen green before merge) and pull requests to `main`. The expected result is
indicative (the count grows as tests are added): **331 passed, 2 xfailed** out of 333
collected, with the Docker-gated seccomp smoke test skipping (330 passed, 1 skipped, 2
xfailed) only when the sandbox image is not yet built. The two `xfailed` are the
decision-0008 in-process forgery vectors in `tests/test_behavior_gate_limits.py`,
pinned known-open; pytest's
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

The v1 in-process subprocess primitive (`sandbox.py`) was retired; the gates route
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
isolation now runs and holds on native Linux in CI (the lockdown probe is green on a
`ubuntu-22.04` + `ubuntu-24.04` cgroup-v2 matrix) as well as macOS Docker Desktop; the
formal native-Linux writeup is done (decision 0030), and what remains open is cgroup v1,
non-Ubuntu distributions, and a kernel-hardening audit. The full model (what the container
closes, the open in-process residual and its trigger condition, the native-Linux
verification, and optional future hardening) is in **[SECURITY.md](SECURITY.md)**.

---

## Stable surface (the 1.0 compatibility boundary)

Darwin 1.0 commits to a **CLI-and-file-format surface**, not to an importable Python API.
Depend on these three things and a future 1.x will not break you:

1. **The six console scripts** — `darwin-loop`, `darwin-mloop`, `darwin-benchmark`,
   `darwin-mbenchmark`, `darwin-variance`, and `darwin-isolation-audit` (their command
   names and documented arguments).
2. **The case directory format** — the on-disk layout of a single-function case under
   `cases/<id>/` (and a multi-file case under `mcases/<id>/`), and the seed inputs
   (`reference.py`, `test_suite.py`, `spec.json`) documented in
   [docs/authoring-a-case.md](docs/authoring-a-case.md).
3. **The dataset JSON schema** — the shape of the committed result and case artifacts
   (for example `reports/v0.9-dataset.json`, `reports/mvariance.json`, `spec.json`,
   `golden_io.json`, `meta.json`).

**Internal modules carry NO import-stability guarantee.** The package ships as
`src/darwin/` and every module under it is importable, but `import darwin.<module>` is
**not** a supported, versioned API: module names, function signatures, and internal
structure may change within the 1.x line without notice. Build on the CLIs and the file
formats above, not on importing internals.

This boundary is stated rather than enforced in code on purpose. A package-level
`__all__` would only govern `from darwin import *`; it does not prevent
`import darwin.<submodule>`, so it cannot express "no import-stability guarantee" and
would misstate the contract. The honest expression is this documented boundary (decision
0046).

---

## Roadmap

Only genuinely remaining work (v1 through v4 are done and merged):

- **Split the trusted emitter out of the candidate's process** to close the
  in-process verdict-forgery residual, required *only* if the gate verdict becomes a
  third-party-trusted artifact (and even then compute-and-lie remains).
- **A multi-distro and kernel-hardening native-Linux audit.** The formal native-Linux
  writeup is done (the SECURITY.md native-Linux section, decision 0030) and CI verifies
  the lockdown on a `ubuntu-22.04` + `ubuntu-24.04` cgroup-v2 matrix; cgroup v1,
  non-Ubuntu distributions, and a kernel-hardening audit remain outstanding before any
  production deployment with untrusted users.
- **Tighter multi-file references and a real-world benchmark.** The multi-file
  references are soft (all 18 of 18 bests sit at or below the floor), and the corpus is
  synthetic and small (30 single-function cases across 7 categories, all hand-authored
  references degraded by the bloat tool, plus 3 medium multi-file cases). Tightening the
  references and drawing a corpus from real-world code is the prerequisite for any
  benchmark-grade claim.
- **A robustness fix to `_require_image`** (the sandbox-image preflight in
  `src/darwin/sandbox_container.py`): it treats any non-zero `docker image inspect` as
  image-absent, so a transient daemon error reads as a missing image rather than a
  daemon problem.
- **Optional defense-in-depth** (a custom seccomp profile, a user-namespace remap).
  Not required for the current threat model; noted as possible future hardening only.

---

## License

Darwin is licensed under the Apache License 2.0. See [LICENSE](./LICENSE).
