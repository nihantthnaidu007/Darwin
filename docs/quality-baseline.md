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

## Coverage (gated as of P7.4; floor re-based to 62 in P8.4)

Coverage is reported by the test job (`--cov=darwin`, term-missing) and gated by
`--cov-fail-under`. Measurement is package-scoped: `[tool.coverage.run] source =
["darwin"]` measures the `src/darwin` package only, and the tests live in `tests/`,
OUTSIDE the package, so they fall out of the measurement naturally. (Before the P8.2
package conversion the flat layout needed a test-file omit so the suite did not measure
itself; that omit is gone.)

The floor was first set to `--cov-fail-under=56` in P7.4 on the flat layout, from
production coverage measured at 58 percent less a 2-point margin (decision 0037). P8.4
re-based it to **`--cov-fail-under=62`** against the package-scoped number:

- Package-scoped production coverage measures about **64.6 percent** under `--cov=darwin`.
  The figure is interpreter-dependent across the 3.12/3.13/3.14 CI matrix: measured
  **64.56 percent** on host Python 3.14.5 and **65.08 percent** on 3.13 (a sub-1-point
  cross-version band; the lowest leg governs the floor). The packaging audit recorded
  64.60 percent, which sits inside that band.
- Floored to 64, less a 2-point cross-version and CI margin, gives **62**. The margin's
  purpose is exactly this cross-version spread: the floor clears the lowest measured leg
  (64.56) with about 2.5 points of headroom, so a leg-to-leg coverage wobble does not
  fail the build while a real coverage regression still does.

The floor stays honest only because the package-scoped measurement excludes the
near-fully-executed test files (they are outside the package): it measures production
coverage, not the suite running itself; counting the test files would inflate the number
and make the gate trivial. See decision 0037.
