# CONTEXT

Per-repo grounding for fresh sessions. Reconstructed from the code and the existing
honest docs. Hard facts only. Read alongside docs/decisions/.

## Purpose

Darwin is a verified code-optimization engine. It takes one working-but-bloated
Python unit, has an LLM simplify it, and objectively verifies the result is correct,
behavior-preserving, and structurally simpler, or returns the original unchanged.
No LLM judges correctness or quality anywhere in the scoring path.

Scope, stated honestly: single-function (v1, tagged v0.1.0) plus OS isolation
(v2.0, tagged v0.2.0); multi-file is merged (v3) and CI plus Linux portability
are merged and tagged 0.3.0 (v4). The never-worse-than-baseline guarantee holds
throughout.

## Domain language

- evaluator: the objective scorer. Three layers in strict order, no LLM. tools/evaluator.py.
- correctness gate (Layer 1): the case pytest suite passes inside the sandbox. Blocking.
- behavior gate (Layer 2): the candidate reproduces every recorded golden pair exactly. Blocking.
- complexity scoring (Layer 3): fixed weighted sum of structural metrics, only for candidates that cleared both gates. Method A in tools/evaluator.py.
- the loop: the directed generate -> evaluate -> feedback cycle. tools/loop.py plus tools/generator.py.
- reference floor: the clean hidden reference version of a case, the structural-complexity target. Score 0.0 at the floor, 1.0 at the bloated original.
- never-worse guarantee: the loop returns the best gate-passing candidate found, or the baseline original if none beats it; never a worse-scoring result by the metric.
- golden I/O: recorded input to output pairs for the behavior gate. golden_io.json per case.
- the container boundary: the locked-down Docker container that every candidate executes inside. The v2.0 security boundary for access. tools/sandbox_container.py.
- the forgery boundary: the candidate and the trusted result-emitter share one process inside the container, so in-process verdict forgery stays open. Access is closed; the verdict is not.
- the one-shot finding: single-function optimization reached the structural floor in generation 1 on every improved case (5 of 5), so the feedback loop was verified but not load-bearing at this scope.
- mcase: a multi-file case. A stateful, order-dependent unit under mcases/.
- sequence corpus: the load-bearing artifact of an mcase. build_corpus() yields (name, ctor_args, calls) sequences over a domain tuned to force state collisions.
- differential testing at the public API: multi-file correctness check. For the same call sequence, original and candidate must produce identical per-call observables on fresh instances.
- the catch-test: an mcase is sound only if its corpus catches every planted break in breaks.py, except breaks marked expect_caught=False (documented irreducible misses). tools/validate_mcase.py.
- comparator conventions: typed equality via canon() (True is not 1), list order observable, dict key order not observable, exception type and message observable. tools/mdiffer.py.
- multi-file evaluator: the multi-file objective scorer. Mirrors the single-function three-layer contract (correctness gate, equivalence gate, complexity scoring) across the container boundary, no LLM. tools/mevaluator.py.
- multi-file metric basket: structural-complexity metrics aggregated across a multi-file unit, the Layer 3 input to the multi-file evaluator. tools/mcase_metrics.py.
- multi-file generator: one model call that rewrites a bloated unit into a candidate package, parsed and statically validated from the model output, never executed on the host. tools/mgenerator.py.
- multi-file loop: the directed generate-evaluate-feedback loop on a multi-file unit. Sanitizes feedback so the generator never sees the oracle. tools/mloop.py.

## Architecture

Single-function stack (v1 plus v2.0 isolation):

- cases/ : materialized cases. Each has original.py, reference.py, test_suite.py, golden_io.json, baseline_metrics.json, meta.json.
- tools/sandbox.py : the v1 in-process subprocess sandbox primitive. Retained in the tree.
- tools/sandbox_container.py : the v2.0 locked-down Docker container primitive. Same contract as sandbox.py across an OS boundary. The gates now route through it.
- tools/verify_case.py : Layer 1 pytest gate then Layer 2 golden-I/O replay. Runs both gates inside the container. The oracle and the comparison stay host-side.
- tools/evaluator.py : Layer 3 objective scoring. Delegates Layers 1 and 2 to verify_case.classify().
- tools/loop.py plus tools/generator.py : the orchestrator (baseline, cap, plateau, never-worse fallback, sanitized feedback) and the single Anthropic generation call.
- tools/benchmark.py : runs the loop over the corpus and aggregates each run's own logs into reports/RESULTS.md and reports/aggregate.json.

Multi-file stack (v3):

- mcases/ : multi-file cases. Each has original/, reference/, corpus.py, test_suite.py, breaks.py, conventions.md, baseline_metrics.json, meta.json.
- tools/mdiffer.py : the differential equivalence core. Promoted from the M0 spike. Reused, not reimplemented, by the verifiers.
- tools/validate_mcase.py : the V0 case validator. Suite, self-equivalence, reference-equivalence, and the catch-test. Trusts both units (in-process).
- tools/mverify.py : the V1 equivalence gate. The candidate is untrusted, so it executes across the container boundary while the original replays host-side and the comparison stays host-side.
- tools/mcase_metrics.py : the V1 multi-file metric basket. Aggregates structural metrics across a unit (the Layer 3 input).
- tools/mevaluator.py : the V1 multi-file evaluator. Three layers in strict order: correctness gate (the case suite inside the container), equivalence gate (mverify), complexity scoring (mcase_metrics against the reference floor). Scored only when both gates pass. No LLM.
- tools/mgenerator.py : the V2 multi-file generator. One model call rewrites the bloated unit into a candidate package, parsed and statically validated from the model output (never executed on the host), path-safe. Reuses generator.py's call machinery.
- tools/mloop.py : the V2 directed multi-file loop. Mirrors loop.py: baseline as guaranteed fallback, generate via mgenerator, score via mevaluator, feed sanitized feedback back (no oracle to the generator), best-kept, never worse than baseline, stop on cap, floor, or plateau.

## Current state

- Version: v4 (CI and hardening), complete and released as 0.3.0. v3 is merged to main (commit 865ec57): the honest multi-file validation report, the six-run variance dataset, and decision 0014 are on main, and the V3 pre-merge and post-merge audits both passed (MAIN HEALTHY).
- Last completed work on main: the v4 merge to main and its post-merge audit. main is green (75 passed, 2 known decision-0008 xfail), all mcases sound, single-function smoke invariants hold.
- v4 (0.3.0) delivered the project's first test-running CI (.github/workflows/ci.yml: build the sandbox image, run the full suite, gating pushes and PRs), plus three hardening items: a pytest-presence guard in validate_mcase; broadening the 3.13-specific wording in README and mverify to the verified 3.12 to 3.14 host range; and a Linux-portability staging fix in tools/sandbox_container.py that makes the per-run read-only bind mount readable and traversable by the container's uid 1000 so the suite runs on native Linux Docker hosts (it previously ran only on macOS Docker Desktop), with the container isolation flags unchanged. v4 added 7 tests, taking the suite from 68 (main before v4) to the current 75 passed, 2 xfailed.
- Roadmap: past 0.3.0, the project is on the production-grade roadmap to a 1.0 release, and milestone M0 (foundation and guardrails) implementation is complete on branch m0-foundation-guardrails. M0 delivered: the Python version metadata reconciled to the verified 3.12 to 3.14 range across pyproject, the trove classifiers, and the README; the non-JSON file reads and writes moved to context managers; the tag-versus-main drift policy recorded (decision 0015: the v0.3.0 tag, commit d1f7123, sits two no-op merge commits behind main, accepted and not re-pointed); and advisory linting (ruff), type checking (mypy), coverage, secret scanning (gitleaks), and a dependency-update bot added in advisory-first mode with a recorded baseline (decision 0016, docs/quality-baseline.md). 0.x stays the honest signal until the open boundaries close (decision 0005).
- Next: the M0 pre-merge audit, the merge to main, and the post-merge audit, then milestone v0.4. The release version is not bumped by M0; it stays 0.3.0 until v0.4 ships.

Open deferred items (honest ledger):

- In-process verdict forgery is deferred. It matters only if the gate verdict becomes a third-party-trusted artifact. Pinned known-open by xfail in tools/test_behavior_gate_limits.py. SECURITY.md.
- Native-Linux isolation now runs and holds in CI. v4 fixed the Linux bind-mount staging (tools/sandbox_container.py) so the container runs on native Linux Docker hosts, and CI (run 27480628605) exercises the container lockdown probes (test_mverify test_probe_confirms_container_lockdown and test_dump_sees_no_original_and_no_outcomes) green on ubuntu-latest, so the isolation is no longer macOS-only. This is one Linux runner, not a multi-distro or kernel-hardening audit; a formal SECURITY.md writeup of the native-Linux verification is still outstanding. SECURITY.md.
- Multi-file equivalence is a strong-but-not-total signal, strictly weaker than single-function golden I/O. The guarantee is sequence-relative and API-relative. reports/M0_EQUIVALENCE.md.
- Per-unit sequence-domain authoring (the corpus reach envelope) is real per-case work, not engineered away. reports/M0_EQUIVALENCE.md, mcases/README.md.
- mverify reads back container stdout capped at 1 MB per stream, used as-is at V1 scope. The fail-closed-on-overflow path is tested (test_mevaluator.py test_outcome_bloated_candidate_fails_closed). tools/mverify.py, tools/sandbox_container.py.
- Module-global load counters (_LOAD) in tools/mverify.py and tools/validate_mcase.py make those importers not concurrency-safe within one process.
- Host Python may range 3.12 to 3.14; the sandbox container is pinned to 3.13 (tools/Dockerfile.sandbox). Cross-version determinism of the canonical equivalence outcomes was verified: the per-call canonical reference outcomes are byte-identical across host 3.12 and 3.14 for all three mcases, so the host-replays-original, container-replays-candidate split is safe across this range. README and tools/mverify.py now state the verified 3.12 to 3.14 host range (the 3.13-specific wording was broadened in v4); done.
- The multi-file loop's feedback sanitizer strips the oracle by matching mevaluator's exact feedback strings (the "original :" line). This is a load-bearing contract between tools/mloop.py and tools/mevaluator.py, not enforced by a shared constant; a regression test in test_mloop guards it by building feedback through the real mevaluator helper. The tests-failed vs could-not-run classifier boundary is part of the same contract.
- Container startup and teardown adds measured overhead (about 0.174 s fixed per spin-up). reports/ISOLATION.md.
- The inverted-span no-signal rule means a candidate that regresses a metric above the original on an inverted-span metric is unscored rather than penalized (decision 0013). A guard flag for "regressed above original" is a future enhancement. tools/evaluator.py.
- The six-run variance dataset (reports/mvariance.json) is hand-recorded summary data, not auto-emitted by the harness. Only the most recent run is independently corroborable from an on-disk artifact (the gitignored maggregate.json); the other five rows are not reproducible from anything retained. Retaining per-run snapshots or a fixed regeneration seed would make all six reproducible if challenged. A v3.1 item. reports/mvariance.json, tools/mbenchmark.py.
- The multi-file references are soft (17 of 18 best candidates at or below floor across the six runs). Tightening them is a prerequisite for any benchmark-grade multi-file claim. reports/MRESULTS.md.

## Conventions

- The evaluator stays objective. No LLM judges correctness or quality anywhere in the scoring path.
- Claims match evidence. The README and docs never outrun the code.
- Every phase gets an independent adversarial audit before merge.
- Never-worse-than-baseline is guaranteed. The loop returns the best gate-passing candidate or the original.
- Honest documentation includes documented known failures and boundaries.
- Multi-file correctness is reported as strong evidence, not proof. Use the sequence-relative and API-relative phrasing.
- Version numbering stays 0.x until genuinely production-grade, then 1.0.
- Formal artifacts use no em dashes and no contractions.
- One branch per phase. Merges to main use --no-ff after a MERGE READY pre-merge audit.
- zsh terminal: save scripts to files and run the files; set environment variables one at a time.
