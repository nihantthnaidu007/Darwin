# Darwin — agent guide

Repo: **nihanthnaidu007/Darwin** (default branch `main`) · Apache-2.0 · v1.0.0
A self-verifying Python code optimizer and reproducible benchmark, single-user-trusted. Darwin takes a working-but-bloated Python unit, asks a model to simplify it, and accepts a candidate **only** if it survives objective verification — correctness gate, behavior-equivalence on frozen golden I/O, and a never-worse-than-baseline structural guarantee. Every candidate executes inside a locked-down Docker container; scoring is LLM-free (radon/vulture metrics).

## Stack

| Layer | What |
|---|---|
| Language | Python ≥ 3.12 (developed on 3.13; host CI matrix 3.12–3.14; sandbox container pinned to 3.13) |
| Package | `darwin` package under `src/darwin` (src layout, 37 modules), hatchling backend; NOT published to PyPI |
| Dependencies | pip + venv, hash-locked: `requirements.txt` (runtime) / `requirements-dev.txt` (dev+CI), installed `--require-hashes`. The `requirements*.in` files are the editable sources — **never hand-edit the generated `.txt` files** |
| Runtime libs | radon 6.0.1, vulture 2.16, pytest 9.0.3, anthropic 0.107.1, httpx 0.28.1 |
| Dev/CI tools | ruff 0.15.17, mypy 2.1.0, pytest-cov 7.1.0, cyclonedx-bom 7.3.0, pip-audit 2.10.1 |
| Infra | **Docker daemon required** to run any candidate through the gates (image `darwin-sandbox:py313`). No database, no ports, no server — pure CLI |

## Commands (from a source checkout)

```bash
# One-time setup
python3 -m venv .venv && source .venv/bin/activate
pip install --require-hashes -r requirements-dev.txt          # supported, hash-locked dev/CI closure
docker build -f docker/Dockerfile.sandbox -t darwin-sandbox:py313 docker/   # required for gated runs

# Quality gates (all blocking in CI)
ruff check src tests
ruff format --check src tests
mypy src tests

# Full test suite (exact CI invocation; coverage gated at 62%)
python -m pytest -q -p no:cacheprovider --cov=darwin --cov-report=term-missing --cov-config=pyproject.toml --cov-fail-under=62

# Primary flows — no API key, no cost
python -m darwin.smoke_test                # every case's reference + original through the REAL Docker gates (end-to-end integration check)
python -m darwin.validate_mcase --all      # validate the multi-file store (no Docker, no key)
python -m darwin.benchmark --report-only   # re-render reports/RESULTS.md from aggregate.json (no API, no Docker)

# Live loop — needs ANTHROPIC_API_KEY, makes real sub-dollar-per-case Anthropic calls
python -m darwin.loop income_tax --cap 5 --plateau 2 --model claude-opus-4-8
python -m darwin.mloop rate_limiter --cap 5 --plateau 2 --model claude-opus-4-8
```

Installed-wheel style (`pip install .`): six console scripts — `darwin-loop`, `darwin-mloop`, `darwin-benchmark`, `darwin-mbenchmark`, `darwin-variance`, `darwin-isolation-audit` — plus `DARWIN_DATA_ROOT=/path/to/checkout`. A source checkout needs neither.

## Env vars

| Var | Required for | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | live loop runs only | gitignored `.env` supported; read-only checks and the test suite make **no** API calls |
| `DARWIN_DATA_ROOT` | installed-wheel CLIs only | from a checkout a walk-up resolver finds `cases/`, `mcases/`, `runs/`, `reports/` on its own |

## Codebase map

See [codebase-map.md](codebase-map.md) (folder-level, depth 2).

## Boundaries to respect

- **Stable surface (1.0):** the six console scripts, the case directory format, and the dataset JSON schema. Internal `darwin.<module>` imports carry **no** stability guarantee — build on CLIs and file formats.
- `cases/`, `mcases/`, `seeds/` are **committed benchmark data**, not project code (excluded from ruff/mypy; their `test_suite.py` files are case data, not project tests). `spikes/` are experiments.
- The candidate sandbox is access-isolated but **not** forgery-proof (in-process verdict-forgery residual, decision 0008 — deferred to 2.0 by design).
- Scoring is a fixed weighted sum of structural metrics with no LLM anywhere in the scoring path; the model never grades its own work.
- CI (`quality.yml`) blocks on any ruff/mypy/gitleaks/pip-audit finding; coverage gate 62% package-scoped.

## Local Verification Summary (onboarding run, 2026-09-17)

| Check | Result |
|---|---|
| `pip install --require-hashes -r requirements-dev.txt` | OK — full hash-verified closure in `.venv` |
| Docker daemon + `docker build -f docker/Dockerfile.sandbox -t darwin-sandbox:py313 docker/` | OK — daemon 26.1.5 (vfs), image built, container execution verified |
| Full pytest suite (CI invocation, cov gate 62%) | **331 passed, 2 xfailed**; coverage 67.19% ≥ 62% |
| `ruff check src tests` | All checks passed (0 findings) |
| `ruff format --check src tests` | 64 files already formatted |
| `mypy src tests` | Success: no issues in 64 source files |
| `python -m darwin.smoke_test` (primary flow, Docker-gated) | **PASSED — 30/30 cases, exit 0** (clean reference passes both gates and beats the bloated original on every case) |
| `python -m darwin.validate_mcase --all` | ALL CASES SOUND |
| `python -m darwin.benchmark --report-only` | exit 0 (re-rendered report; committed `reports/RESULTS.md` restored to HEAD afterwards) |
| Live LLM loop (`darwin-loop` / `darwin-mloop`) | NOT exercised — requires `ANTHROPIC_API_KEY` and incurs real API cost; TODO(confirm) before a live run |

**dev_stack_healthy: true** — verified end-to-end with evidence above.

## Sandbox snapshot

- **snapshotId:** `iwgvrjgmf897exb95jojr`
- **captured:** 2026-09-17T15:59:10.463Z
- **contains:** repo at `fab9d08` on `main`; `.venv` with the hash-locked dev closure; Docker daemon running with `darwin-sandbox:py313` built; full suite, gates, and smoke test already verified green.
