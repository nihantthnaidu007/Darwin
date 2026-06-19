# Darwin v0.9 Corpus Expansion: Methodology Contract

Status: DRAFT for review. This document is the contract for the v0.9 milestone. It is
authored and committed before any case is sampled, authored, or run. The git commit of
this file predates every reference and every run artifact in the milestone. That temporal
ordering is itself an integrity guarantee and is mechanically verifiable.

In this milestone the methodology is the deliverable. The cases are its evidence.

---

## 1. Purpose and the exact claim

v0.9 exists to convert one finding from a 5-case anecdote into a population-level result
the project can defend: that at single-function scope, capable-model optimization is
effectively one-shot, and Darwin's multi-generation directed-feedback loop is not
load-bearing there. The current RESULTS.md states this honestly off 5 cases and flags the
corpus size as the headline limitation. v0.9 removes that limitation by expanding to 25 to
30 cases under a stated, outcome-blind methodology.

### The claim v0.9 will make

Across N (target 25 to 30) pure single-function cases sampled from permissively-licensed
open-source code under the protocol below, with each case run R = 5 times:

- The generation that produced the returned best candidate (`best_gen`) is reported per
  case as a distribution over the 5 runs.
- The population-level statement is the measured fraction of cases whose best arrives in
  generation 1, with its run-to-run variance.

### The claim v0.9 will NOT make

- It will not claim Darwin makes code "better" by any subjective standard. The engine
  scores structural complexity reduction that the correctness and behavior gates verify,
  nothing more.
- It will not claim the directed loop is load-bearing at single-function scope. If the
  expanded corpus confirms the one-shot finding, the claim is precisely that the loop is
  NOT load-bearing here, which is a finding against the engine's own headline mechanism
  and is reported as such.
- It will not make a benchmark-grade claim about real-world optimization in general. The
  population is pure, dependency-light utility and algorithmic functions, not all code.

### Primary versus secondary findings, and why the split matters

- PRIMARY (floor-robust): the generation-count finding (`best_gen`). Which generation
  produced the lowest-cost candidate is largely insensitive to where the reference floor
  is set, because the floor rescales magnitude rather than reordering candidates across
  generations. This is the headline claim and it is the most defensible one.
- SECONDARY (floor-dependent): the magnitude finding ("bloat removed", the fraction of the
  original-to-floor span closed). This depends directly on the authored reference floor and
  therefore carries the authored-reference risk in full. It is reported with that caveat
  stated inline and is never the headline. Path 1 magnitudes will be SMALLER than the
  existing synthetic corpus by construction: real functions are naturally messy at low
  double-digit complexity, not bloated to the cyclomatic-50 range of the synthetic
  originals, so the original-to-floor span is narrower. A smaller, real-world magnitude is
  more honest, not a regression, and the writeup frames it that way explicitly.

The strongest claim is also the most defensible one. That is deliberate.

---

## 2. Scope constraints (forced by the machinery, not chosen)

These are not preferences. They follow from the oracle and from licensing reality.

1. PURITY. The behavior gate is golden-I/O replay. It requires functions that are
   deterministic and pure: no I/O, no randomness, no global or class state, no nondeter
   minism. The sampled population is therefore the pure, dependency-light subset of real
   code: parsers, formatters, encoders, date and number math, string utilities, pure
   algorithms. This is narrower than "open-source code" and the disclosure says so.

2. LICENSE. Only permissively-licensed sources (MIT, BSD, Apache 2.0). Per-case provenance
   (source repository, file, license, commit or version) is recorded in each case's
   `meta.json` under a `provenance` block. No copyleft (GPL, AGPL, LGPL) source is admitted.

---

## 3. Sampling protocol (outcome-blind, fixed before any run)

The integrity of the whole milestone rests on selection being blind to Darwin's
performance. The predicate below is a property of the input function, never of Darwin's
output on it.

### Qualification predicate

A candidate function qualifies if and only if ALL hold, measured on the ORIGINAL function
before any Darwin run:

- It is pure and deterministic per Section 2, with a definable argument-set for golden-I/O
  capture.
- It is self-contained: it depends only on the standard library and on nothing in its host
  repository that cannot be inlined without changing behavior.
- It meets a stated structural-complexity threshold, fixed here before sampling and
  calibrated against the existing corpus: cyclomatic complexity >= 6 OR logical lines of
  code >= 20, measured on the real sampled function (the original) before any Darwin run.
  A function below both is too trivial to exercise the engine and does not qualify. The
  threshold is set on the scale of real, naturally-written functions, not on the inflated
  scale of the existing synthetically-bloated originals (whose cyclomatic values reach the
  40s and 50s precisely because the mess was injected). A real qualifying function is
  expected to land in roughly the cyclomatic 6 to 20, logical-LOC 20 to 60 band.
- Its source license is permissive per Section 2.

### Selection rule

- Every sampled function that meets the predicate is admitted and stays in the corpus,
  regardless of how Darwin later performs on it. A case where Darwin returns baseline, or
  does nothing, is a data point, not a defect to exclude.
- No function is added or removed after seeing a Darwin run on it. Sampling and admission
  complete before the first run.

### Category distribution

The existing taxonomy is retained: `verbose_patterns`, `duplication`, `excessive_nesting`,
`over_abstraction`, `unnecessary_dependency`, `dead_code`. Target a roughly even spread,
approximately 5 cases per category across a difficulty range (easy, medium, hard), fixed
before building so composition is not chosen post hoc. The category is recorded per case in
`meta.json`. The existing 5 cases are retained and counted; v0.9 adds approximately 20 to
reach 25 to 30.

---

## 4. Reference-authoring standard (the load-bearing protocol)

Path 1 inverts the existing reference-first pipeline. The real function is the `original`;
the clean `reference.py` is authored. The authored reference defines the 0.0 floor, so this
is the single largest integrity surface in the milestone. Three rules govern it, each
provable by git rather than by trust.

### The reference rubric (committed before any reference is authored)

A reference is the behavior-preserving cleanup of the original that satisfies ALL of:

- Preserves the public contract exactly: same signature, same return values, same raised
  exceptions on the same inputs. Verified by the case's test suite and golden I/O.
- Removes dead code and unreachable branches.
- Collapses redundant or duplicated control flow.
- Uses idiomatic standard-library constructs in place of hand-rolled equivalents.
- Optimizes for readability, NOT for character count. Code-golf is explicitly disallowed.
- Is defined by these structural and readability criteria, which are INDEPENDENT of what a
  model can reach in a single generation. The reference is never authored down to a
  one-shot-reachable target. This is what prevents the one-shot finding from being an
  artifact of the floor.

### Temporal freeze (the mechanical guarantee)

- Every `reference.py` is authored and committed BEFORE the first Darwin run of the
  milestone. The git commit timestamp of each reference predates the first run artifact.
  This is verifiable after the fact and is the strongest single integrity fact in v0.9.

### Disclosure (the honest hedge)

- The methodology and the results disclose plainly that references were authored to this
  pre-committed rubric and frozen before any run, name authored-reference bias as a known
  limitation, and explain the two mitigations: the temporal freeze, and the floor-robustness
  of the primary (generation-count) finding. Disclosure of a known assumption beats a hidden
  one. This matches the existing RESULTS.md ethos.

### A note on who authors the reference

Authoring a reference with assistance (including an LLM) is permitted ONLY if done to the
rubric above and committed before any Darwin run. The integrity does not rest on who wrote
the reference; it rests on (a) the rubric being independent of one-shot reachability and
(b) the temporal freeze. An independently authored reference that happens to converge with
Darwin's output is evidence the floor is real and reachable, not a problem.

---

## 5. Run protocol

- Each case is run R = 5 times under the standard loop configuration (the same cap and
  plateau settings used for the existing RESULTS.md, recorded in the results header).
- Per case, the distribution of `best_gen` over the 5 runs is reported, not a single draw.
  This converts "one-shot" from a single observation into a measured low-variance result
  and exposes any case where the loop IS load-bearing some of the time.
- Cost estimate, derived from the existing RESULTS.md logged totals (approximately
  USD 0.03 per single-function case per run): on the order of USD 4 to 5 for 28 cases at 5
  runs. This estimate is verified against a small batch (for example 2 cases at 5 runs)
  before committing the full run. The estimate is not a claim; it is checked against real
  spend.

---

## 6. Honesty and disclosure guarantees (absolute, pre-committed)

- v0.9 reports the FULL distribution: every case, including every case where Darwin returns
  baseline, does nothing, or where the loop unexpectedly was load-bearing.
- If the expanded corpus breaks the one-shot finding in some cases, the result is reported
  as "one-shot in X of N cases, with the exceptions named and characterized." A clean N of
  N is not a goal and would be reported with the same scrutiny applied to a mixed result.
- No case is excluded, no metric is suppressed, and no number is reported that is not
  reproducible from a committed artifact, consistent with the project's existing standard.

---

## 7. What v0.9 does NOT establish (the standing limits)

v0.9 strengthens one empirical claim. It changes none of the following, and the 1.0 that
follows must not imply otherwise:

- The in-process verdict-forgery boundary remains open, disclosed, and deferred to 2.0
  (decision 0008). v0.9 is not a security milestone.
- Darwin's posture remains single-user-trusted. v0.9 does not make it multi-tenant-safe.
- The directed loop's value at multi-file and system scope is a separate question (the
  v0.9-B path that was considered and deferred). v0.9 sharpens the single-function finding
  only.

---

## 8. Acceptance criteria for this contract

This document is accepted and committed when:

- The claim (Section 1), the sampling predicate (Section 3), the reference rubric and freeze
  (Section 4), the run protocol (Section 5), and the disclosure guarantees (Section 6) are
  reviewed and agreed.
- It is committed to the repository before any case is sampled or authored.

Only after this contract is committed does the build-phase decomposition begin.
