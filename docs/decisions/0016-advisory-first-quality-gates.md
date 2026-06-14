# 0016 Advisory-first quality gates: non-blocking until findings reach zero

Decision: The P0.2 quality gates (ruff lint and format check, mypy, coverage, and the gitleaks secret scan) are introduced as advisory, not blocking. Each CI job runs and surfaces its findings in the Actions UI but uses continue-on-error so it never fails the workflow or blocks a merge; coverage is reported with no --cov-fail-under. The gates flip to blocking in P7.2, once the recorded baseline findings have been driven to zero across the intervening phases.

Context: Darwin is a several-thousand-line codebase (36 source files in tools/) that had never been linted or type-checked and carries no type annotations. The recorded baseline on 2026-06-14 is 10 ruff lint findings, 36 files that ruff format would reformat, and 2 mypy errors (docs/quality-baseline.md). Making the gates blocking on day one would halt all feature work behind a large cleanup, and a single big reformat-and-annotate commit would bury real review signal and risk behavior changes in untyped code. Advisory-first lets each later phase shape its own area to standard while the baseline numbers fall, with the gates measuring progress the whole way.

Alternatives rejected:
- Blocking gates from the start: would stop work on the existing debt immediately, against the milestone's intent to make later phases measurable rather than to halt them.
- A one-shot cleanup commit to reach zero now, then block: a repo-wide reformat plus annotation pass is high-risk on untyped code, mixes mechanical churn with substantive diffs, and is out of M0 scope (P0.2 explicitly records a baseline, it does not clean it).
- Leaving the gates out until P7.2: forgoes the per-phase measurement and the standard-shaping pressure that advisory gates provide across the intervening phases.

Consequences: CI is green even while findings are open, so the baseline counts, not the workflow status, are the signal to watch; docs/quality-baseline.md is the reference the later phases drive toward zero. P7.2 owns the flip to blocking and must confirm the counts are zero before enabling it. The dependency-update bot activates only on the default branch, so its first PR appears after M0 merges to main.
