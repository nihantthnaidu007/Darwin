# Quality baseline

Status of the quality gates introduced in P0.2 (advisory then, blocking as of P7.4),
for the production code in tools/ (cases/ and spikes/ are excluded; see
pyproject.toml). The gates were advisory on purpose: halting work on a
several-thousand-line untyped, never-linted codebase on day one would have been wrong
(decision 0016). P7.3 drove all three to zero; P7.4 flipped them from advisory to
blocking, so they are blocking now -- a finding fails its job and blocks the merge
(decision 0037).

- Tooling (pinned in requirements-dev.txt): ruff 0.15.17, mypy 2.1.0, pytest-cov 7.1.0
- Config: [tool.ruff], [tool.mypy], [tool.coverage.run] in pyproject.toml

## Current numbers (cleared)

- Date cleared: 2026-06-18 (P7.3)
- Scope: tools/ only

| Gate | Command | Result |
|------|---------|--------|
| ruff lint | `ruff check tools/` | 0 findings (all checks passed) |
| ruff format | `ruff format --check tools/` | 0 would reformat (all files formatted) |
| mypy | `mypy tools/` | 0 errors (59 source files checked) |

### Exact output

```
$ ruff check tools/
All checks passed!

$ ruff format --check tools/
59 files already formatted

$ mypy tools/
Success: no issues found in 59 source files
```

## How zero was reached (P7.3, three isolated commits)

Decision 0016 recorded these gates as advisory and assumed the intervening phases
would drive them down incrementally; they did not. P7.3 cleared them in three
isolated commits, so the large mechanical reformat never buried the small semantic
fixes:

- P7.3a: `ruff format tools/`, pure mechanical formatting. This also resolved the
  4 E702 multiple-statements-on-one-line findings, which the formatter owns
  (it deterministically splits semicolon-joined simple statements).
- P7.3b: cleared the remaining ruff lint findings at root, fixed not suppressed
  (no noqa, no per-file ignore): 3 unused imports, 2 empty f-strings, and 1 unused
  variable.
- P7.3c: added the 2 missing `_results` type annotations
  (verify_container_sandbox.py and verify_boundary.py) for a clean mypy, and
  refreshed this document.

## Recorded starting baseline (historical)

The starting baseline recorded on 2026-06-14, before any cleanup:

| Gate | Command | Result |
|------|---------|--------|
| ruff lint | `ruff check tools/` | 10 errors (5 fixable) |
| ruff format | `ruff format --check tools/` | 36 files would be reformatted |
| mypy | `mypy tools/` | 2 errors in 2 files (36 source files checked) |

Both mypy errors were the `_results` list assigned with no element type at module
scope in verify_container_sandbox.py and verify_boundary.py.

Reconciliation of the file counts: the 2026-06-14 snapshot above is "36 files would
be reformatted / 36 source files checked," taken when tools/ held 36 files. By v0.7
the tree had grown to 59 source files, because files were added in v0.5 and v0.6; the
P7.3a format pass accordingly reformatted 55 of those 59 (the other 4 were already
compliant) and mypy now checks 59 (see Current numbers above). The growth is real new
code, not a measurement change, and all three findings are at zero on the larger count.

## Coverage (gated as of P7.4)

Coverage is reported by the test job (`--cov`, term-missing) and gated as of P7.4 at
`--cov-fail-under=56`. The floor is set from production coverage measured at 58
percent, less a 2-point cross-version and CI margin, so the test job now fails on a
coverage drop below 56 as well as on a test failure or an unexpected pass. The floor
is honest only because the `--cov-config` omit excludes the near-fully-executed test
files: it measures production coverage, not the suite running itself; counting the
test files would inflate the number and make the gate trivial. The 56 value is fixed
here and not re-tuned in this close-out. See decision 0037.
