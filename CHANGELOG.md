# Changelog

All notable changes to Darwin, newest first. Darwin is installed from a local checkout
(`pip install .`) or run from source, and GitHub-tagged (it is not published to PyPI);
each release is tagged from its merge commit on main. Versions stayed in the 0.x line
through 0.9; 1.0 is the freeze under a single-user-trusted posture, which reframes
decision 0005's original 1.0 criteria: 1.0 commits to a reproducible single-user-trusted
benchmark, with the in-process verdict-forgery boundary still open by design and deferred
to 2.0 (decision 0046).

Note: there is no 0.4.0 release. The v0.4.0 tag was mis-created on the M0 merge
commit (M0 does not bump the version) and is annotated with the M0 milestone name;
it contains none of the v0.4 work. Per the never-force-push-tags rule (decisions
0015 and 0005) it is treated as void and left in place, so the first 0.4.x release
is 0.4.1. See decision 0020.

## 1.0.0, the freeze

The 1.0 freeze. Documentation, version metadata, and one new authoring doc only: no
change to the optimization, scoring, equivalence, gate, `build_case`, dataset, or case
behavior. The single non-doc change is the version bump.

- **Tagged 1.0 as a single-user-trusted reproducible benchmark and engine (framing b).**
  1.0 reframes decision 0005's original 1.0 criteria: it commits to a reproducible
  single-user-trusted benchmark, **not** to closing the in-process verdict-forgery
  boundary. That boundary stays **open by design** and is deferred to 2.0 (decisions 0008,
  0046). 1.0 is **not** a capability change and does **not** support running on untrusted
  code and trusting the verdict (framing (a) is 2.0 work).
- **Results reconciled to the v0.9 evidence.** The freeze carries forward the P10.1
  reconciliation: the authoritative 30-case single-function finding (143 of 150 runs =
  95.3 percent one-shot, `reports/RESULTS.md` / `reports/v0.9-dataset.json`) and the
  artifact-backed multi-file variance dataset (`reports/mvariance.json` /
  `reports/MRESULTS.md`, decision 0035). Every number traces to a committed artifact.
- **Trust posture and threat model finalized.** `SECURITY.md` and the README agree on the
  single-user-trusted 1.0 posture. The `SECURITY.md` title now reads as the 1.0 posture,
  and a numbering note disambiguates the container access-isolation boundary generation
  (labeled `v2.0` in that document) from the Darwin release line. Nothing implies 1.0
  closes the forgery boundary.
- **Benchmark made externally extendable.** A user-facing case-authoring schema,
  `docs/authoring-a-case.md`, specifies how an external author writes a new single-function
  case (the seed inputs, the `spec.json` schema field by field, the reference rubric, and
  the build command) without reading `build_case.py`, verified against the
  `seeds/roman_to_int/` seed.
- **Stable 1.0 surface declared.** The stable surface is the six console scripts, the case
  directory format, and the dataset JSON schema; internal `darwin.<module>` imports carry
  no import-stability guarantee. Stated as a documented boundary, not a package `__all__`
  (which would govern only star-imports and misstate the contract) (decision 0046).
- **Freeze polish.** Cleared the readiness-audit stale items: the native-Linux `SECURITY.md`
  writeup and the multi-file variance-snapshot retention are stated as done (decisions
  0030, 0035), and the CI suite count is refreshed to the measured 331 passed / 2 xfailed
  out of 333 collected.

## 0.9.0, corpus expansion

Grew the single-function corpus from the retired 5-case validation set to a 30-case
synthetic corpus and ran it under one frozen config to produce the authoritative
one-shot finding. Run-and-record only: no change to the optimization, scoring,
equivalence, gate, `build_case`, or default-lockdown behavior.

- **30-case synthetic single-function corpus.** The single-function corpus expanded to
  30 hand-authored cases degraded by the bloat tool, spread across seven degradation
  categories (over_abstraction 6, defensive_overengineering 5, unnecessary_dependency 5,
  duplication 4, verbose_patterns 4, dead_code 3, excessive_nesting 3) and three
  difficulties (easy 11, medium 12, hard 7). The corpus is synthetic: both ends of the
  measured span are authored (the tool-bloated original and the hand-authored reference
  floor), so the claim is about controlled degradations, not real-world code. This is
  the headline limitation (decision 0043).
- **Seventh category, `defensive_overengineering`.** Amendment 1 added
  `defensive_overengineering` as the seventh degradation category (decision 0044). The
  earlier ordering claim was corrected during the freeze audit: the two cases
  `first_or_default` and `normalize_scores` were entered at `96a681d`, about 6h51m
  before Amendment 1 at `2f2cd74`; the prior claim is struck, not erased, not back-dated.
- **Authoritative one-shot finding (143/150, 95.3 percent).** The frozen corpus ran
  under one fixed config (cap=5, plateau=2, 5 runs per case = 150 runs), model
  `claude-opus-4-8`, temperature 1.0. Across the 150 runs, 143 (95.3 percent) reached
  the returned-best candidate in generation 1 (`best_gen` distribution gen 1: 143,
  gen 2: 4, gen 3: 3). This is the authoritative 30-case confirmation of the one-shot
  finding (decision 0006) that the 5-case validation set could only suggest, and it
  supersedes that grounding (decision 0045). The loop's role is run-to-run near-floor
  variance, not function shape: the 7 later-generation runs span three unrelated
  categories. Total cost $2.601205 across 150 runs. Every number traces to
  `reports/v0.9-dataset.json`; `reports/RESULTS.md` is the narrative authority.
- **Methodology switch to run-and-record.** The path switched from authoring new
  optimization machinery to running the frozen corpus under a fixed config and recording
  the result, with no engine, scoring, gate, or `build_case` change in the measured run
  (decision 0043).
- **Corpus-wide temporal-freeze proof.** Every case was frozen before it was run: all
  freeze commits are ancestors of the dataset git HEAD (`8b2dd60`), and the committed
  `original.py` is byte-identical to the scored generation-0 input in all 150 runs. See
  `reports/v0.9-temporal-freeze.md`.

## 0.8.0, packaging

Converted Darwin from flat `tools/` scripts to an installable `darwin` package, added a
build-system and console scripts, deferred all data-root resolution out of import time,
and re-based the coverage floor to the package-scoped number. No change to the
optimization, scoring, equivalence, or default-lockdown behavior.

- **Flat-to-package conversion.** The flat `tools/` scripts became an importable
  `darwin` package under `src/darwin/`, with the test suite moved to `tests/` (outside
  the package), bare imports rewritten to absolute `darwin.*` imports, and a single
  `paths.py` data-root resolver. The resolver finds the `cases/`, `mcases/`, `runs/`,
  and `reports/` data directories by walking UP from a starting file to the first
  ancestor holding a marker (`pyproject.toml` or `cases/`), so resolution is correct
  regardless of how deeply a module is nested. To run an installed CLI, set
  `DARWIN_DATA_ROOT` to the data root; the `--cases-dir` / `--mcases-dir` / `--out` flags
  override only their own lookup (a checkout-side convenience) and do not on their own
  satisfy an installed run, which also resolves `runs/` (and `reports/`) under the data root.
- **Build-system and six console scripts.** A `[build-system]` table (hatchling,
  configured for the src layout) makes `pip install .` build a wheel that ships only the
  `darwin` package (no `cases/`, `mcases/`, or `docker/`). The install puts six
  `darwin-*` console scripts on `PATH`: `darwin-loop`, `darwin-mloop`,
  `darwin-benchmark`, `darwin-mbenchmark`, `darwin-variance`, and
  `darwin-isolation-audit`. The four non-argparse harnesses (`bakeoff`, `smoke_test`,
  `build_case`, `validate_mcase`) get no console script by design and stay
  `python -m darwin.<name>` dev tools.
- **Import-time data resolution deferred (PEP 562).** Resolving a data path at import
  was a defect: an installed CLI has no checkout on disk, so a module that called
  `paths.cases_dir()` at module scope crashed on `import` (or on `--help`) before
  argparse could supply `--cases-dir` / `DARWIN_DATA_ROOT`. Every module now defers data
  resolution to first attribute access via a PEP 562 lazy module-attribute
  (`__getattr__`), so no `src/darwin` module does filesystem work at import; the
  attributes stay settable, so a caller or a test can still pin them. P8.3 deferred the
  six console-script entry points; this release deferred the last four harnesses
  (`bakeoff`, `smoke_test`, `build_case`, `validate_mcase`).
- **Two install paths.** The supported, reproducible install is the hash-locked
  `requirements.txt` installed with `--require-hashes` (decision 0028, intact). The
  `pip install .` wheel is a convenience path: it resolves `[project].dependencies` as
  version ranges, NOT the hash-locked closure, so it is not for reproducible or
  security-reviewed installs. Neither path publishes to PyPI (decisions 0040 and 0041).
- **Coverage floor re-based to 62.** The old `--cov-fail-under=56` was set on the flat
  layout. With coverage now package-scoped (`--cov=darwin`), production coverage measures
  about 64.6 percent (64.56 on host Python 3.14, 65.08 on 3.13); the floor was re-based
  to `--cov-fail-under=62` (64 floored, less a 2-point cross-version margin). See
  docs/quality-baseline.md and decision 0037.

## 0.7.0, test and CI maturity

Hardened the test and CI surface: cleared the one known dependency CVE, added
direct unit tests for the two orchestration cores, drove the quality gates to zero
and flipped them to blocking, and validated the host-Python range with a real CI
matrix. No change to the optimization, scoring, equivalence, or default-lockdown
behavior.

- **pytest 9 bump clears CVE-2025-71176.** pytest moves from 8.3.5 to 9.0.3 across
  the runtime, dev/CI, and sandbox closures, clearing CVE-2025-71176 (the finding
  the v0.6 advisory pip-audit scan surfaced). The locks were recompiled on the
  canonical Python 3.13 (decision 0028), which pulled `pygments==2.20.0` in as a new
  transitive of pytest into the runtime (`requirements.txt`) and sandbox
  (`tools/requirements-sandbox.txt`) closures. No other dependency moved
  (decision 0036).
- **Direct unit tests for the loop and the single-function verifier.** New direct
  tests for `loop.py` (never-worse-than-baseline fallback, the generation cap, and
  plateau stop) and `verify_case.py` (the Layer 1 then Layer 2 gate ordering, the
  withheld oracle, and the failing-gate taxonomy), bringing both to 99 percent line
  coverage.
- **Quality gates driven to zero and flipped to blocking.** The four gates -- ruff
  lint, ruff format, mypy, and the gitleaks secret scan -- plus the pip-audit
  dependency scan were driven to zero findings and flipped from advisory to blocking,
  so a finding now fails its job and blocks the merge (decision 0037).
- **Coverage gate at 56 percent.** A `--cov-fail-under=56` floor was added to the
  test job, set from production coverage measured at 58 percent (the `--cov-config`
  omit excludes the test files) less a 2-point cross-version and CI margin
  (decision 0037).
- **Python 3.12/3.13/3.14 CI matrix.** The test job runs the full suite on a host
  matrix of Python 3.12, 3.13, and 3.14 (`fail-fast: false`), each leg installing the
  single hashed dev lock under `--require-hashes` and building the sandbox image at
  Python 3.13. The single lock was confirmed to install across all three interpreters
  (3.12 Linux, 3.13 Linux CI, 3.14 macOS), so no per-version locks were introduced
  (decision 0038).
- **A v0.6.1 tag was pushed in error and then deleted.** During the P5.3b merge (the
  authorized variance regeneration that closed F1), a `v0.6.1` tag was briefly pushed
  to origin in error and then removed. Deleting a published tag deviates from the
  never-force-push-or-delete-tags rule (decisions 0005 and 0015); this was a
  deliberate operator action, recorded here plainly rather than hidden. P5.3b carries
  no tag by design (it changed no version). This is distinct from the void v0.4.0 tag,
  which was left in place: v0.6.1 was deleted (decision 0039).

## 0.6.0, supply-chain and isolation hardening

Closed A2, G2, and A4, and delivered A3 (opt-in defense-in-depth plus the
verdict-emission seam). No change to the optimization, scoring, equivalence, or
default-lockdown behavior.

- **A2, reproducible image boundary.** The sandbox base image is pinned by its
  multi-arch manifest-list digest (not the mutable `python:3.13-slim` tag), with a
  documented rotation procedure, so a rebuild pulls the exact same base and the
  boundary cannot change under us between builds (decision 0027).
- **A2/G2, hash-locked dependencies, an SBOM, and a vulnerability scan.** Hash-locked
  lockfiles (pip-tools, `--generate-hashes`) for the host, CI, and the sandbox image,
  installed everywhere with `--require-hashes` (decision 0028); a CycloneDX SBOM of
  the runtime surface uploaded as a CI build artifact; and an advisory pip-audit
  dependency vulnerability scan in CI (decision 0029). The scan surfaced pytest
  CVE-2025-71176; the pytest 9 bump is deferred to P7.2 (v0.7), to land before or with
  the scan's flip to blocking.
- **A4, native-Linux isolation verification.** A CI matrix (`.github/workflows/isolation.yml`)
  exercises the container lockdown probe across two Ubuntu runners (ubuntu-22.04 and
  ubuntu-24.04) on cgroup v2, recording each runner's actual cgroup version, kernel,
  and Docker version, with the probe's exit code gating each leg; a native-Linux
  section in SECURITY.md is scoped to exactly that recorded evidence (decision 0030).
- **A3, opt-in defense-in-depth.** Opt-in, off-by-default plumbing to append extra
  container `--security-opt` entries (a seccomp profile and related hardening), with
  the default `docker run` argv **byte-identical** when unset, and an example
  starting-point seccomp profile (a labeled starting point, **not** a validated
  production profile); the multi-tenant hardening posture (seccomp, daemon-level user
  namespaces, block-IO and file-size caps) is documented in SECURITY.md (decision 0033).
- **A3, the verdict-emission seam.** A typed `VerdictEmitter` interface with an
  in-process default and a serializable verdict (`MEvaluation.to_dict`/`from_dict`),
  with the multi-file consumers retyped to it: the explicit forward-commitment so the
  2.0 out-of-process emitter swaps in by replacing one component, touching no consumer
  (decision 0032).
- **A1 remains open by design.** In-process verdict forgery (the candidate and the
  trusted result-emitter share one process) stays open at 1.0, a non-issue for the
  single-user-trusted use and pinned by the decision-0008 xfail vectors; the
  VerdictEmitter seam above is now in place to receive its 2.0 out-of-process fix.

## 0.5.0, correctness, determinism, and reproducibility

Closed C1, D1, and N2 in full, and closed F1 on configuration and machinery with
the artifact-backed variance regeneration deferred. No change to the optimization,
scoring, or equivalence behavior.

- **C1, feedback materiality.** `feedback_load_bearing` redefined with a documented
  materiality threshold (a later generation's gain must clear a 0.5 percentage-point
  floor to count), and reports/aggregate.json regenerated so the machine-readable
  artifact agrees with the prose (decision 0021).
- **F1, configuration and determinism.** Temperature pinned explicitly to 1.0 and
  full run provenance (temperature, model, SDK version, and request params) recorded
  in run.json, so a result traces to its exact configuration (decision 0022).
- **F1, reproducibility machinery.** A variance harness with snapshot persistence
  that derives the variance table from committed per-run snapshots (decision 0023).
  The artifact-backed regeneration of the multi-file variance (P5.3b) is deferred to
  an authorized run, so the committed variance numbers remain the 2026-06-13
  hand-recorded dataset until then.
- **D1, concurrency-safe evaluator state.** Dynamic-import module names minted from
  uuid across all three eval-path loaders (mverify, validate_mcase, mdiffer),
  removing the module-global counters; the container path is confirmed
  concurrency-safe by unique names and fresh temp dirs; production evaluation is
  still sequential (decision 0024).
- **N2, oracle-sanitization contract.** The oracle witness prefixes bound to a shared
  marker across the producer (mevaluator) and the sanitizer (mloop), with a
  real-producer oracle-leak test as the standing guarantee that fails if a wording
  change or misroute would expose the oracle to the generator (decision 0025).

## 0.4.1, resilience and operability

Closed four findings. No change to the optimization, scoring, or equivalence
behavior.

- **B1, LLM-call resilience and resumable runs.** Hardened the LLM calls with an
  explicit timeout, bounded retries, a shared retryable-versus-fatal error
  taxonomy, and a model-capability fallback; added resumable checkpointed runs that
  persist each completed case as it finishes and refuse a config-mismatched resume.
- **B2, image preflight false-negative.** The image preflight now tolerates the
  inspect-by-tag false negative via a listing fallback, so a present image is not
  reported missing.
- **E1, structured logging.** Structured logging across the core path, with a
  readable console handler on stderr and a JSON handler, the RUN SUMMARY report
  preserved on stdout (decision 0018).
- **N1, input and artifact validation.** Guarded JSON loading and case and mcase
  shape validation on the run-path readers, so a missing or malformed input fails
  with a clear, file-naming error instead of a raw traceback or a downstream
  KeyError; the simulated-attack payload exhibits are left as authored.

## 0.3.0, first test-running CI and hardening

- The project's first test-running CI: it builds the sandbox image and runs the
  full suite, gating pushes and pull requests on ubuntu-latest.
- A pytest-presence guard in validate_mcase.
- Broadened the host-version wording to the verified 3.12 to 3.14 range.
- A Linux-portability bind-mount staging fix so the container runs on native Linux
  Docker hosts, not only macOS Docker Desktop.
