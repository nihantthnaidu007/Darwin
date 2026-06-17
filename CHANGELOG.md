# Changelog

All notable changes to Darwin, newest first. Darwin is run from source and
GitHub-tagged (it is not published to PyPI); each release is tagged from its merge
commit on main. Versions stay in the 0.x line until the open boundaries from
decision 0005 close.

Note: there is no 0.4.0 release. The v0.4.0 tag was mis-created on the M0 merge
commit (M0 does not bump the version) and is annotated with the M0 milestone name;
it contains none of the v0.4 work. Per the never-force-push-tags rule (decisions
0015 and 0005) it is treated as void and left in place, so the first 0.4.x release
is 0.4.1. See decision 0020.

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
