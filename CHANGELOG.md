# Changelog

All notable changes to Darwin, newest first. Darwin is run from source and
GitHub-tagged (it is not published to PyPI); each release is tagged from its merge
commit on main. Versions stay in the 0.x line until the open boundaries from
decision 0005 close.

## 0.4.0, resilience and operability

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
