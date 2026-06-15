# Quality baseline

Recorded baseline of the advisory quality gates introduced in P0.2. These are
the actual current numbers for the production code in tools/. Later phases drive
each toward zero before P7.2 flips the gates from advisory to blocking. The gates
are advisory now on purpose: halting work on a several-thousand-line untyped,
never-linted codebase on day one would be wrong.

- Date recorded: 2026-06-14
- Scope: tools/ only (cases/ and spikes/ are excluded; see pyproject.toml)
- Tooling (pinned in requirements-dev.txt): ruff 0.15.17, mypy 2.1.0, pytest-cov 7.1.0
- Config: [tool.ruff], [tool.mypy], [tool.coverage.run] in pyproject.toml

## Numbers

| Gate | Command | Result |
|------|---------|--------|
| ruff lint | `ruff check tools/` | 10 errors (5 fixable) |
| ruff format | `ruff format --check tools/` | 36 files would be reformatted |
| mypy | `mypy tools/` | 2 errors in 2 files (36 source files checked) |

## Exact output

```
$ ruff check tools/
...
Found 10 errors.
[*] 5 fixable with the `--fix` option (1 hidden fix can be enabled with the `--unsafe-fixes` option).

$ ruff format --check tools/
...
36 files would be reformatted

$ mypy tools/
tools/verify_container_sandbox.py:26: error: Need type annotation for "_results" (hint: "_results: list[<type>] = ...")  [var-annotated]
tools/verify_boundary.py:59: error: Need type annotation for "_results" (hint: "_results: list[<type>] = ...")  [var-annotated]
Found 2 errors in 2 files (checked 36 source files)
```

## Notes

- No source file was edited to lower any of these numbers. This is a recorded
  baseline, not a cleanup. `ruff check --fix` and `ruff format` (without
  `--check`) were not run. Adding type annotations was out of scope.
- Coverage is reported by the test job (`--cov`, term-missing) but not gated:
  there is no `--cov-fail-under`, so the test gate still fails only on a test
  failure or an unexpected pass. The measured starting point at this date was
  TOTAL 29 percent over the 27 non-test files in tools/ (test files omitted),
  recorded here for reference only and not driven by this phase.
