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
reproducibility (v0.5) bumped the release to 0.5.0 (decision 0026); and supply-chain
and isolation hardening (v0.6) bumps it to 0.6.0 (decision 0034); and test and CI
maturity (v0.7) bumps it to 0.7.0 (decision 0039).
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

- Version: 0.7.0 (v0.7, test and CI maturity), complete on branch v0.7-test-ci-maturity and recorded by this close-out; 0.7.0 will be tagged at its merge commit on main after the merge and the post-merge audit, the next package (decision 0039). It stays in the 0.x line because the open boundaries from decision 0005 are not yet closed. The prior release is 0.6.0 (v0.6, decision 0034); before it 0.5.0 (v0.5, decision 0026) and 0.4.1 (v0.4); there is no 0.4.0 release (the v0.4.0 tag is a void mis-tag on the M0 merge, left in place per the never-force-push-tags rule, decisions 0015 and 0020). A v0.6.1 tag was pushed in error on the P5.3b merge and then deleted, a recorded deviation from the never-delete-tags rule; P5.3b carries no tag by design (decision 0039). The highest decision record is 0039; the 0031 gap is intentional and left as-is. The coverage gate floor is --cov-fail-under=56 (decision 0037).
- Last completed work: the v0.7 milestone (P7.1 through P7.5 plus this close-out) on branch v0.7-test-ci-maturity, branched from the v0.6 merge. v0.7 hardened the test and CI surface: the pytest 8.3.5 to 9.0.3 bump cleared CVE-2025-71176 and re-locked on Python 3.13 (pulling pygments in as a new transitive; decision 0036); direct unit tests for loop.py and verify_case.py reached 99 percent line coverage each (P7.2); the four quality gates (ruff lint and format, mypy, gitleaks) plus pip-audit were driven to zero and flipped to blocking, with a --cov-fail-under=56 coverage floor set from measured 58 percent less 2 (decision 0037); and a Python 3.12/3.13/3.14 host CI matrix on the single hashed lock backs the documented host range (decision 0038). No change to the optimization, scoring, equivalence, or default-lockdown behavior.
- v0.6 closed A2, G2, and A4 and delivered A3 (CHANGELOG.md, decision 0034): A2 -- the sandbox base image pinned by manifest-list digest with a documented rotation procedure (decision 0027); A2/G2 -- hash-locked lockfiles (pip-tools, --generate-hashes) for the host, CI, and the sandbox image installed with --require-hashes, a CycloneDX SBOM build artifact, and an advisory pip-audit vulnerability scan in CI (decisions 0028, 0029); A4 -- a CI matrix exercising the container lockdown probe across two Ubuntu runners (ubuntu-22.04, ubuntu-24.04) on cgroup v2, recording the actual cgroup version, with a native-Linux SECURITY.md section scoped to that evidence (decision 0030); A3 -- opt-in, off-by-default seccomp plumbing with a byte-identical default argv and an example starting-point profile (decision 0033), plus the typed VerdictEmitter seam with an in-process default and a serializable verdict, the forward-commitment for the 2.0 out-of-process emitter (decision 0032). A1 in-process verdict forgery remains open by design at 1.0, now with the VerdictEmitter seam in place to receive its 2.0 fix (decision 0008).
- The v0.6 advisory pip-audit scan surfaced pytest CVE-2025-71176 (present in the runtime and sandbox closures); v0.7 cleared it by the pytest 8.3.5 to 9.0.3 bump (decision 0036) and then flipped the pip-audit and quality gates from advisory to blocking on the now-clean closure (decision 0037), honoring the v0.6 coupling that the bump land before or with the blocking flip.
- Suite: 257 passed, 2 xfailed, plus one Docker-gated skip when the daemon is absent (the gated test runs and passes when the image is present, for 258 passed). The 2 xfails are the known decision-0008 forgery-boundary exhibits. All mcases sound, single-function smoke invariants hold. The Docker-gated tests run when the sandbox image is present, via the preflight that tolerates the inspect-by-tag false negative.
- Earlier history on main: v0.5 (correctness, determinism, reproducibility) closed C1, D1, N2 and F1's configuration and machinery and released as 0.5.0 with the artifact-backed variance regeneration (P5.3b) deferred (decisions 0021-0026); v0.4 (resilience and operability) closed B1, B2, E1, N1 and released as 0.4.1 (decisions 0019, 0020); M0 (foundation and guardrails) merged at 4cff555 with advisory-first quality tooling (ruff, mypy, coverage, gitleaks, a dependency-update bot; decision 0016) and bumped no version; v3 (multi-file) merged at 865ec57 with the honest validation report and the six-run variance dataset (decision 0014); v4 (CI and Linux portability) delivered the first test-running CI (.github/workflows/ci.yml) and the Linux bind-mount staging fix. Each passed its pre-merge and post-merge audits.
- Next: the merge of v0.7 to main and the 0.7.0 tag at the merge commit, after a MERGE READY pre-merge audit and the post-merge audit (decision 0039); the following milestone is unscheduled. P5.3b (the authorized variance regeneration run) is done: it ran on 2026-06-17 and regenerated reports/mvariance.json and reports/MRESULTS.md from six committed snapshots under reports/variance_runs/, fully closing F1 (decision 0035); a v0.6.1 tag was pushed in error on its merge and then deleted (decision 0039).

Open deferred items (honest ledger):

- In-process verdict forgery is deferred. It matters only if the gate verdict becomes a third-party-trusted artifact. Pinned known-open by xfail in tools/test_behavior_gate_limits.py. SECURITY.md.
- Native-Linux isolation is verified in CI (v0.6, P6.3, decision 0030). A dedicated matrix (.github/workflows/isolation.yml) runs the container lockdown probe on ubuntu-22.04 and ubuntu-24.04, both cgroup v2, recording each runner's cgroup version, kernel, and Docker version, with the probe's exit code gating each leg; SECURITY.md carries a native-Linux section scoped to that recorded evidence. cgroup v1 and non-Ubuntu distributions are not exercised (hosted runners are Ubuntu on cgroup v2); a real v1 or alternate-distribution run is a documented self-hosted / VM follow-up. SECURITY.md.
- Multi-file equivalence is a strong-but-not-total signal, strictly weaker than single-function golden I/O. The guarantee is sequence-relative and API-relative. reports/M0_EQUIVALENCE.md.
- Per-unit sequence-domain authoring (the corpus reach envelope) is real per-case work, not engineered away. reports/M0_EQUIVALENCE.md, mcases/README.md.
- mverify reads back container stdout capped at 1 MB per stream, used as-is at V1 scope. The fail-closed-on-overflow path is tested (test_mevaluator.py test_outcome_bloated_candidate_fails_closed). tools/mverify.py, tools/sandbox_container.py.
- Host Python may range 3.12 to 3.14; the sandbox container is pinned to 3.13 (tools/Dockerfile.sandbox). Cross-version determinism of the canonical equivalence outcomes was verified: the per-call canonical reference outcomes are byte-identical across host 3.12 and 3.14 for all three mcases, so the host-replays-original, container-replays-candidate split is safe across this range. README and tools/mverify.py now state the verified 3.12 to 3.14 host range (the 3.13-specific wording was broadened in v4). v0.7 added a CI matrix that runs the full suite on host Python 3.12, 3.13, and 3.14, each leg on the single hashed lock with the sandbox image fixed at 3.13 (decision 0038), backing this range with continuous evidence; done.
- The multi-file loop's feedback sanitizer now strips the oracle by the shared witness prefixes in tools/oracle_markers.py, imported by both the producer (tools/mevaluator.py) and the sanitizer (tools/mloop.py), and guarded by a real-producer oracle-leak test (tools/test_oracle_leak.py, decision 0025). Residual: the verdict and gate routing-key literals the sanitizer branches on are still bare and duplicated across producer and sanitizer (the reason codes are shared); they are guarded by the same leak test, which fails if their drift causes a misroute, and sharing them is a follow-up.
- Container startup and teardown adds measured overhead (about 0.174 s fixed per spin-up). reports/ISOLATION.md.
- The inverted-span no-signal rule means a candidate that regresses a metric above the original on an inverted-span metric is unscored rather than penalized (decision 0013). A guard flag for "regressed above original" is a future enhancement. tools/evaluator.py.
- The variance-reproducibility harness (tools/variance_harness.py, decision 0023) persists each run's maggregate.json as a committed snapshot under reports/variance_runs/ and derives the variance dataset from those snapshots, deterministically. The artifact-backed regeneration (P5.3b) ran on 2026-06-17 (decision 0035): six committed snapshots under reports/variance_runs/run_00 .. run_05 now back reports/mvariance.json, which derive regenerates byte-identically, and reports/MRESULTS.md is regenerated from them. The 2026-06-13 hand-recorded dataset is superseded and F1 is fully closed. reports/mvariance.json, reports/variance_runs/, tools/variance_harness.py.
- The multi-file references are soft (all 18 of 18 best candidates at or below floor across the six 2026-06-17 runs; decision 0035). Tightening them is a prerequisite for any benchmark-grade multi-file claim. reports/MRESULTS.md.

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
