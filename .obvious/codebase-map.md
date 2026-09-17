# Darwin — codebase map

Folder-level overview of nihanthnaidu007/Darwin (depth 2). The engine is 37 modules in `src/darwin`; `cases/` and `mcases/` are committed benchmark data, not source.

| Path | Kind | What lives there |
|---|---|---|
| `.github/workflows/` | CI | `ci.yml` — build sandbox image, pytest matrix on Python 3.12/3.13/3.14 with coverage gate 62%, CycloneDX SBOM job; `quality.yml` — blocking ruff lint+format, mypy, gitleaks, pip-audit; `isolation.yml` — container lockdown probe on cgroup v2; `claude.yml` + `claude-code-review.yml` — Claude automation; `dependabot.yml` |
| `assets/` | docs | `darwin-banner.svg` — README banner |
| `cases/` | data | 30 single-function benchmark cases across 7 degradation categories. Each `cases/<id>/`: `original.py` (bloated input), `reference.py` (hand-authored clean target), `test_suite.py` (correctness gate), `golden_io.json` (behavior oracle), `baseline_metrics.json`, `meta.json` |
| `docker/` | infra | `Dockerfile.sandbox` — the candidate sandbox image (base pinned by python:3.13-slim manifest-list digest); `requirements-sandbox.in` / `.txt` — hash-locked in-container deps (stdlib + pytest only); `seccomp/example-sandbox-seccomp.json` — opt-in seccomp starting profile |
| `docs/` | docs | `authoring-a-case.md` (how to author a new case), v0.9 corpus methodology, `quality-baseline.md` (gate baselines), `decisions/` — 45 ADRs (0001–0046, the project's decision log) |
| `mcases/` | data | 3 multi-file cases — `doc_history`, `rate_limiter`, `task_scheduler`. Each has `reference/` and `original/` package trees, `test_suite.py`, `breaks.py` (planted-break probes), `meta.json`, `baseline_metrics.json` |
| `reports/` | results | `RESULTS.md` (the findings report), `v0.9-dataset.json` (authoritative dataset), `aggregate.json` (single-function results), `mvariance.json`, temporal-freeze + methodology reports, `variance_runs/` |
| `seeds/` | data | 30 seed inputs for authoring new cases: `reference.py`, `test_suite.py`, `spec.json` per seed |
| `spikes/` | research | throwaway experiments (`m0/`: ablation, differ, run_spike); excluded from lint/type targets |
| `src/darwin/` | code | the importable package. Engine: `loop.py`, `mloop.py`, `evaluator.py`, `mevaluator.py`, `verify_case.py`, `mverify.py`, `generator.py`, `mgenerator.py`, `llm_client.py`. Sandbox/isolation: `sandbox_container.py`, `verify_container_sandbox.py`, `isolation_audit.py`, `verdict_emitter.py`, `verify_boundary.py`. Harnesses: `benchmark.py`, `mbenchmark.py`, `variance_harness.py`, `bakeoff.py`, `smoke_test.py`. Case tooling: `bloat.py`, `build_case.py`, `build_real_case.py`, `record_golden.py`, `freeze_metrics.py`, `validate_mcase.py`, `mdiffer.py`. Shared: `paths.py`, `runstate.py`, `runinput.py`, `logsetup.py`, `report.py`, `oracle_markers.py`, `feedback_materiality.py`, metrics modules |
| `tests/` | code | 27 pytest modules mirroring the package — loop/mloop orchestrators, evaluators, sandbox argv + container, verdict emitter, provenance, oracle leak, behavior-gate forgery limits (xfail), concurrency, checkpoint, harness smoke |
| root | manifests | `pyproject.toml` (hatchling build, six console scripts, ruff/mypy/pytest/coverage config), `requirements.in`/`.txt` + `requirements-dev.in`/`.txt` (pip-tools hash-locked), `README.md`, `CHANGELOG.md`, `CONTEXT.md`, `SECURITY.md` (threat model), `LICENSE` |
