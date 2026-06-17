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
