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
are merged and tagged 0.3.0 (v4); foundation and guardrails (M0) and resilience
and operability (v0.4) are merged and released 0.4.1 (there is no 0.4.0 release;
the v0.4.0 tag was a mis-tag, decision 0020); correctness, determinism, and
reproducibility (v0.5) are merged, bumping the release to 0.5.0 (decision 0026).
The never-worse-than-baseline guarantee holds throughout.

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

- Version: 0.5.0 (v0.5, correctness, determinism, and reproducibility), complete on branch v0.5-correctness and recorded by this close-out; 0.5.0 is tagged at its merge commit on main after the merge and the post-merge audit (decision 0026). It stays in the 0.x line because the open boundaries from decision 0005 are not yet closed. The prior release is 0.4.1 (v0.4); there is no 0.4.0 release (the v0.4.0 tag is a void mis-tag on the M0 merge, left in place per the never-force-push-tags rule, decisions 0015 and 0020).
- Last completed work: the v0.5 milestone (P5.1 through P5.5) on branch v0.5-correctness, branched from the v0.4 merge. No change to the optimization, scoring, or equivalence behavior.
- v0.5 closed four findings (CHANGELOG.md, decision 0026): C1 -- feedback_load_bearing redefined with a documented materiality threshold (a later-generation gain must exceed 0.5 percentage points) and reports/aggregate.json regenerated to agree with the prose (decision 0021); D1 -- dynamic-import module names minted from uuid across all three eval-path loaders (mverify, validate_mcase, mdiffer), removing the module-global counters, the container path confirmed concurrency-safe by unique names and fresh temp dirs, production evaluation still sequential (decision 0024); N2 -- the oracle witness prefixes bound to a shared marker (tools/oracle_markers.py) across producer (mevaluator) and sanitizer (mloop), guarded by a real-producer oracle-leak test (decision 0025). F1 is closed on configuration and determinism (temperature pinned explicitly to 1.0 with full run provenance -- temperature, model, SDK version, request params -- recorded in run.json, decision 0022) and on the reproducibility machinery (a variance harness with committed-snapshot persistence that derives the variance table from snapshots, decision 0023); the artifact-backed regeneration of the multi-file variance (P5.3b) is deferred to an authorized run and parked on authorization, so the committed reports/mvariance.json numbers remain the 2026-06-13 hand-recorded dataset until then.
- Suite: 208 passed, 1 skipped, 2 xfailed. The 2 xfails are the known decision-0008 forgery-boundary exhibits; the 1 skip is the Docker-image-gated mloop integration test (test_mloop.py), skipped when the image-inspect probe reads unavailable and run otherwise. All mcases sound, single-function smoke invariants hold.
- Earlier history on main: v0.4 (resilience and operability) closed B1, B2, E1, N1 and released as 0.4.1 (decisions 0019, 0020); M0 (foundation and guardrails) merged at 4cff555 with advisory-first quality tooling (ruff, mypy, coverage, gitleaks, a dependency-update bot; decision 0016) and bumped no version; v3 (multi-file) merged at 865ec57 with the honest validation report and the six-run variance dataset (decision 0014); v4 (CI and Linux portability) delivered the first test-running CI (.github/workflows/ci.yml) and the Linux bind-mount staging fix. Each passed its pre-merge and post-merge audits.
- Next: milestone v0.6 (supply-chain): digest pinning, a lockfile with hashes, and the verdict-emission seam. P5.3b (the authorized variance regeneration run) is parked on authorization and lands when that spend is approved.

Open deferred items (honest ledger):

- In-process verdict forgery is deferred. It matters only if the gate verdict becomes a third-party-trusted artifact. Pinned known-open by xfail in tools/test_behavior_gate_limits.py. SECURITY.md.
- Native-Linux isolation now runs and holds in CI. v4 fixed the Linux bind-mount staging (tools/sandbox_container.py) so the container runs on native Linux Docker hosts, and CI (run 27480628605) exercises the container lockdown probes (test_mverify test_probe_confirms_container_lockdown and test_dump_sees_no_original_and_no_outcomes) green on ubuntu-latest, so the isolation is no longer macOS-only. This is one Linux runner, not a multi-distro or kernel-hardening audit; a formal SECURITY.md writeup of the native-Linux verification is still outstanding. SECURITY.md.
- Multi-file equivalence is a strong-but-not-total signal, strictly weaker than single-function golden I/O. The guarantee is sequence-relative and API-relative. reports/M0_EQUIVALENCE.md.
- Per-unit sequence-domain authoring (the corpus reach envelope) is real per-case work, not engineered away. reports/M0_EQUIVALENCE.md, mcases/README.md.
- mverify reads back container stdout capped at 1 MB per stream, used as-is at V1 scope. The fail-closed-on-overflow path is tested (test_mevaluator.py test_outcome_bloated_candidate_fails_closed). tools/mverify.py, tools/sandbox_container.py.
- Host Python may range 3.12 to 3.14; the sandbox container is pinned to 3.13 (tools/Dockerfile.sandbox). Cross-version determinism of the canonical equivalence outcomes was verified: the per-call canonical reference outcomes are byte-identical across host 3.12 and 3.14 for all three mcases, so the host-replays-original, container-replays-candidate split is safe across this range. README and tools/mverify.py now state the verified 3.12 to 3.14 host range (the 3.13-specific wording was broadened in v4); done.
- The multi-file loop's feedback sanitizer now strips the oracle by the shared witness prefixes in tools/oracle_markers.py, imported by both the producer (tools/mevaluator.py) and the sanitizer (tools/mloop.py), and guarded by a real-producer oracle-leak test (tools/test_oracle_leak.py, decision 0025). Residual: the verdict and gate routing-key literals the sanitizer branches on are still bare and duplicated across producer and sanitizer (the reason codes are shared); they are guarded by the same leak test, which fails if their drift causes a misroute, and sharing them is a follow-up.
- Container startup and teardown adds measured overhead (about 0.174 s fixed per spin-up). reports/ISOLATION.md.
- The inverted-span no-signal rule means a candidate that regresses a metric above the original on an inverted-span metric is unscored rather than penalized (decision 0013). A guard flag for "regressed above original" is a future enhancement. tools/evaluator.py.
- The variance-reproducibility harness now exists (tools/variance_harness.py, decision 0023): it persists each run's maggregate.json as a committed snapshot under reports/variance_runs/ and derives the variance dataset from those snapshots, deterministically (tested on synthetic snapshots). The artifact-backed regeneration (P5.3b) is parked on authorization; until that authorized run populates the snapshots, reports/mvariance.json remains the 2026-06-13 hand-recorded dataset (its note says so). reports/mvariance.json, tools/variance_harness.py.
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
