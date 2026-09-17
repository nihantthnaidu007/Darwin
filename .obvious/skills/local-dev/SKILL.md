---
name: local-dev
description: Bring nihanthnaidu007/Darwin to a working local dev environment — venv with hash-locked deps, Docker daemon plus the darwin-sandbox:py313 image — and verify with the full suite, the blocking quality gates, and the Docker-gated smoke test.
---

# local-dev — Darwin onboarding record

Recorded 2026-09-17 by the autobuild onboarding worker. Everything below was executed and verified on sandbox snapshot `iwgvrjgmf897exb95jojr` (repo at `fab9d08` on `main`, Python 3.13.14, Debian 13).

## What this repo needs

- Python ≥ 3.12 (3.13 is the reference host) and pip + venv.
- **Docker** — required to run any candidate through the gates. Without the `darwin-sandbox:py313` image, 21 tests fail with `RuntimeError: sandbox image 'darwin-sandbox:py313' not found` and 5 more skip.
- `ANTHROPIC_API_KEY` **only** for live LLM loop runs — the test suite uses fakes; all read-only checks make no API calls.

## Steps that worked

1. **Install deps (supported path):**
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install --require-hashes -r requirements-dev.txt   # runtime + ruff/mypy/pytest-cov/pip-audit
   ```
2. **Docker daemon** (this sandbox ships without one):
   ```bash
   sudo apt-get install -y docker.io
   sudo nohup dockerd --host=unix:///var/run/docker.sock --storage-driver=vfs > /tmp/dockerd.log 2>&1 &
   sudo chmod 666 /var/run/docker.sock   # or add user to the docker group (needs a fresh shell)
   docker run --rm hello-world           # proves container execution actually works
   ```
3. **Build the sandbox image (one-time):**
   ```bash
   docker build -f docker/Dockerfile.sandbox -t darwin-sandbox:py313 docker/
   ```
4. **Full suite (CI invocation):**
   ```bash
   python -m pytest -q -p no:cacheprovider --cov=darwin --cov-report=term-missing --cov-config=pyproject.toml --cov-fail-under=62
   ```
   Expected: 331 passed, 2 xfailed, coverage ~67% (gate 62%). Takes ~3.5 min (hundreds of `docker run` calls).
5. **Quality gates:** `ruff check src tests` · `ruff format --check src tests` · `mypy src tests` — all zero findings.
6. **Primary flows (no key, no cost):** `python -m darwin.smoke_test` (30/30 cases through the real gates, ~4 min) · `python -m darwin.validate_mcase --all` (ALL CASES SOUND) · `python -m darwin.benchmark --report-only` (exit 0).

## Gotchas

- `usermod -aG docker` does not refresh groups in an existing shell — `chmod 666` the socket or wrap commands in `sg docker -c '…'`.
- `python -m darwin.benchmark --report-only` **rewrites the tracked `reports/RESULTS.md`** (drift vs the committed render). Restore with `git checkout -- reports/RESULTS.md` after using it.
- pytest config lives in `pyproject.toml` (`pythonpath = ["src"]`, `testpaths = ["tests"]`) — run pytest from the repo root; `cases/`/`mcases/` `test_suite.py` files are data and are not collected.
- `runs/`, `reports/maggregate.json`, `.venv/`, `dist/` are gitignored outputs — never commit them.
- `requirements*.txt` are generated (pip-tools, `--generate-hashes`); edit only the `.in` sources and recompile on Python 3.13.
- The smoke test and suite launch hundreds of short `docker run` calls; the vfs storage driver keeps them reliable on this sandbox class.
- Live loop runs (`python -m darwin.loop <case> …`) cost real money (sub-dollar per case) and need `ANTHROPIC_API_KEY` — TODO(confirm) with the owner before running one.

## Verification evidence (2026-09-17)

| Check | Result |
|---|---|
| Hash-locked dev install | OK |
| Docker + sandbox image | OK (daemon 26.1.5, vfs; image built; hello-world ran) |
| pytest suite | 331 passed, 2 xfailed; coverage 67.19% ≥ 62% |
| ruff check / format --check | 0 findings / 64 files clean |
| mypy src tests | no issues in 64 files |
| `python -m darwin.smoke_test` | PASSED 30/30, exit 0 |
| `python -m darwin.validate_mcase --all` | ALL CASES SOUND |
| `python -m darwin.benchmark --report-only` | exit 0 |

dev_stack_healthy: true
