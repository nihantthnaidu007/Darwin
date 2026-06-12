# CONTEXT

Per-repo grounding for fresh sessions. Reconstructed from the code and the existing
honest docs. Hard facts only. Read alongside docs/decisions/.

## Purpose

Darwin is a verified code-optimization engine. It takes one working-but-bloated
Python unit, has an LLM simplify it, and objectively verifies the result is correct,
behavior-preserving, and structurally simpler, or returns the original unchanged.
No LLM judges correctness or quality anywhere in the scoring path.

Scope, stated honestly: single-function (v1, tagged v0.1.0) plus OS isolation
(v2.0, tagged v0.2.0), extending to multi-file (v3, in progress). The
never-worse-than-baseline guarantee holds throughout.

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

## Current state

- Version: v3. Branch v3-v1-multifile-evaluator.
- Last completed work: V1 Prompt 2, the full multi-file evaluator, tools/mevaluator.py (correctness gate, containerized equivalence gate, structural scoring, specific feedback), plus tools/mcase_metrics.py for the metric basket.
- Working today: v1 single-function simplifier (tagged v0.1.0); v2.0 OS isolation (tagged v0.2.0); v3 in progress (M0 equivalence spike done, V0 multi-file case store done, V1 multi-file evaluator done across both prompts). Verified: validate_mcase --all reports ALL CASES SOUND, and the 20 container-backed multi-file tests pass.

Open deferred items (honest ledger):

- In-process verdict forgery is deferred. It matters only if the gate verdict becomes a third-party-trusted artifact. Pinned known-open by xfail in tools/test_behavior_gate_limits.py. SECURITY.md.
- Native-Linux isolation verification is pending. Isolation was verified on macOS Docker Desktop only. SECURITY.md.
- Multi-file equivalence is a strong-but-not-total signal, strictly weaker than single-function golden I/O. The guarantee is sequence-relative and API-relative. reports/M0_EQUIVALENCE.md.
- Per-unit sequence-domain authoring (the corpus reach envelope) is real per-case work, not engineered away. reports/M0_EQUIVALENCE.md, mcases/README.md.
- mverify reads back container stdout capped at 1 MB per stream, used as-is at V1 scope. The fail-closed-on-overflow path is tested (test_mevaluator.py test_outcome_bloated_candidate_fails_closed). tools/mverify.py, tools/sandbox_container.py.
- Module-global load counters (_LOAD) in tools/mverify.py and tools/validate_mcase.py make those importers not concurrency-safe within one process.
- Container startup and teardown adds measured overhead (about 0.174 s fixed per spin-up). reports/ISOLATION.md.

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
