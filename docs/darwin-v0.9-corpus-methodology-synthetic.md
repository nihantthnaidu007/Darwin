# Darwin v0.9 Corpus Expansion: Methodology Contract (Synthetic Path)

Status: DRAFT for review. This document SUPERSEDES the Path-1 (real open-source) contract
committed at P9.0. It is the contract for the v0.9 milestone under the synthetic,
reference-first construction path. It is authored and committed before any new case is
built. The git commit of this file predates every new reference and every run artifact in
the milestone.

In this milestone the methodology is the deliverable. The cases are its evidence.

---

## Revision note: why this supersedes the Path-1 contract

The Path-1 contract specified sampling real open-source functions and authoring a clean
reference for each. Building the pilot surfaced a structural tension in that path before any
case was authored: clean, well-licensed library functions have a near-zero optimization span
(they are clean precisely because they are maintained), while messy functions with a real
span tend to have unusable provenance (tutorial or recipe code with murky licensing). Real,
pure, permissively-licensed, AND meaningfully-improvable standalone functions are a narrow
and slow-to-source population. The pilot did its job: it exposed the methodology cost before
the human effort was spent.

The milestone therefore switches to the synthetic, reference-first construction the existing
5-case corpus already uses: a clean reference is authored, and the `bloat` tool degrades it
into the messy original. This is the path the existing tooling (`build_case.py`) supports
directly. The Path-1 construction tool (`build_real_case.py`) and its license gate, built in
P9.1 and P9.2a, remain in the tree as completed, tested work, superseded for this milestone.
That history is recorded in the P9.5 decision records. The switch is disclosed, not hidden.

---

## 1. Purpose and the exact claim

v0.9 converts one finding from a 5-case anecdote into a result with statistical weight: that
at single-function scope, capable-model optimization is effectively one-shot, and Darwin's
multi-generation directed-feedback loop is not load-bearing there. The current RESULTS.md
states this honestly off 5 cases and flags the corpus size as the headline limitation. v0.9
removes that limitation by expanding to 25 to 30 controlled synthetic cases.

### The claim v0.9 will make

Across N (target 25 to 30) controlled single-function cases spanning the six complexity
categories, where each original is a known degradation of an authored clean reference
produced by the `bloat` tool, with each case run R = 5 times:

- The generation that produced the returned best candidate (`best_gen`) is reported per case
  as a distribution over the 5 runs.
- The population-level statement is the measured fraction of cases whose best arrives in
  generation 1, with its run-to-run variance.

### The claim v0.9 will NOT make

- It will NOT claim "real-world", "open-source", or "production" code. The corpus is
  synthetic by construction: authored references degraded by a tool. This is stated in every
  results surface.
- It will not claim the originals represent how humans write bad code. They represent how the
  `bloat` tool degrades good code, which is a narrower and different distribution.
- It will not claim the directed loop is load-bearing at single-function scope. If the
  expanded corpus confirms the one-shot finding, the claim is precisely that the loop is NOT
  load-bearing here, a finding against the engine's own headline mechanism, reported as such.

### Primary versus secondary findings

- PRIMARY (robust): the generation-count finding (`best_gen`). Which generation produced the
  lowest-cost candidate is the headline. It is robust to the authored floor (the floor
  rescales magnitude rather than reordering candidates across generations) and it is the
  measure the milestone is built to strengthen.
- SECONDARY (doubly synthetic, reported with caveat): the magnitude finding ("bloat removed",
  the fraction of the original-to-floor span closed). In the synthetic path this is doubly
  synthetic: the floor is an authored reference AND the ceiling is a tool-generated
  degradation. It therefore measures "how much injected mess the engine reversed", not "how
  much real bloat it removed". It is reported with that double caveat stated inline and is
  never the headline.

---

## 2. Construction constraints

1. PURITY. The behavior gate is golden-I/O replay, which requires deterministic, pure
   functions: no I/O, no randomness, no global or class state. Because references are
   authored (not sampled), this is satisfied by authoring pure functions. It remains a hard
   requirement on every authored reference.
2. NO LICENSE CONSTRAINT. The synthetic path samples no real source code, so the permissive-
   license constraint of the Path-1 contract does not apply. No third-party code enters the
   corpus.

---

## 3. Reference-pattern selection (the composition is fixed before building)

The synthetic path has no real-function sampling. What is "selected" is which clean reference
patterns to author, across the six complexity categories. The anti-bias mechanism is that the
category composition is fixed before any case is built, so the corpus cannot be composed after
the fact to flatter the finding.

### Category distribution (committed before building)

The existing taxonomy is retained: `verbose_patterns`, `duplication`, `excessive_nesting`,
`over_abstraction`, `unnecessary_dependency`, `dead_code`. Target a roughly even spread,
approximately 5 cases per category across a difficulty range (easy, medium, hard), fixed
here before building. The existing 5 cases are retained and counted toward the 25 to 30; v0.9
authors approximately 20 new references to reach the target. Category and difficulty are
recorded per case in `meta.json`.

### Non-triviality

Each authored reference is a non-trivial representative of its category, and the `bloat` step
must inject a substantial original-to-reference span (a case with no span has nothing to
measure). The existing corpus shows the achievable span (original cyclomatic in the 25 to 51
range over reference cyclomatic in the 3 to 13 range). New cases target a comparably
substantial span. This is an authoring-discipline requirement; `build_case.py` does not gate
on span, so the author is responsible for it.

### No outcome-based exclusion

Every case that is built and passes construction stays in the corpus, regardless of how
Darwin performs on it. A case where Darwin returns baseline, or reaches best at generation 1,
or unexpectedly improves at generation 2, is a data point, not a result to exclude. No case
is removed after seeing a run on it.

---

## 4. Reference-authoring standard and synthetic integrity guarantees

The author writes the clean `reference.py`; the `bloat` tool generates `original.py` from it.
The reference defines the 0.0 floor and the original defines the 1.0 anchor.

### The reference rubric (committed before any reference is authored)

A reference is a clean, idiomatic, behavior-correct function that:

- Defines a clear public contract (signature, return values, raised exceptions).
- Is the readable, idiomatic form a careful engineer would write: dead code removed,
  redundant control flow collapsed, standard-library constructs used in place of hand-rolled
  equivalents, optimized for readability not character count. No code-golf.
- Is defined by these structural and readability criteria, which are INDEPENDENT of what a
  model can reach in a single generation. The reference is never authored down to a
  one-shot-reachable target. This independence is what prevents the one-shot finding from
  being an artifact of the floor.

### The integrity guarantees specific to the synthetic path

1. The degradation is TOOL-GENERATED, not hand-crafted. The `bloat` tool produces the
   original from the reference. The author does not hand-write an original chosen to be
   trivially reversible. This keeps the injected mess out of the author's control over the
   outcome.
2. The category composition is FIXED before building (Section 3), so the corpus cannot be
   assembled post hoc to flatter the finding.
3. References are committed BEFORE their runs (temporal freeze). Every reference commit
   predates every run artifact; this is verified in P9.5.
4. The full distribution is reported (Section 6), including every case where Darwin returns
   baseline or where the loop is load-bearing.

### Disclosure

Every results surface states plainly that the corpus is synthetic: authored references
degraded by a tool, not real-world code. The synthetic nature is named as the headline
limitation, the same way the current RESULTS.md names the 5-case size as its limitation.
Disclosure of a known construction is the standard; a hidden one is not.

---

## 5. Run protocol

- Each case is run R = 5 times under one fixed loop configuration (the cap and plateau
  settings, recorded in the results header).
- Per case, the distribution of `best_gen` over the 5 runs is reported, not a single draw.
  This converts "one-shot" from a single observation into a measured low-variance result and
  exposes any case where the loop is load-bearing some of the time.
- Cost estimate, derived from the existing RESULTS.md logged totals (approximately USD 0.03
  per single-function case per run): on the order of USD 4 to 5 for 28 cases at 5 runs. This
  estimate is verified against the pilot batch before the full run. The estimate is checked
  against real spend, not asserted.

---

## 6. Honesty and disclosure guarantees (absolute, pre-committed)

- v0.9 reports the FULL distribution: every case, including every case where Darwin returns
  baseline, reaches best at generation 1, or improves later.
- If the expanded corpus breaks the one-shot finding in some cases, the result is reported as
  "one-shot in X of N cases, with the exceptions named and characterized." A clean N of N is
  not a goal.
- No case is excluded, no metric is suppressed, and no number is reported that is not
  reproducible from a committed artifact.

---

## 7. What v0.9 does NOT establish (the standing limits)

- The corpus is synthetic. v0.9 makes no claim about real-world or open-source code.
- The in-process verdict-forgery boundary remains open, disclosed, and deferred to 2.0
  (decision 0008). v0.9 is not a security milestone.
- Darwin's posture remains single-user-trusted. v0.9 does not make it multi-tenant-safe.
- The directed loop's value at multi-file and system scope is a separate question. v0.9
  sharpens the single-function finding only.

---

## 8. Acceptance criteria for this contract

This document is accepted and committed when:

- The claim (Section 1), the category composition (Section 3), the reference rubric and the
  synthetic integrity guarantees (Section 4), the run protocol (Section 5), and the
  disclosure guarantees (Section 6) are reviewed and agreed.
- It is committed to the repository, superseding the Path-1 contract, before any new case is
  built.

Only after this contract is committed does the pilot (P9.3) begin.

---

## Amendment 1 (2026-06-20): seventh category, defensive_overengineering

The original contract (Section 3) fixed the category taxonomy at six categories before
building. During corpus authoring, a seventh distinct anti-pattern surfaced that none of the
six captures cleanly: defensive_overengineering, the wrapping of simple correct logic in
excess validation (per-element isinstance checks, try/except around arithmetic that cannot
raise, None guards on values that cannot be None, redundant re-validation after computation).
This is structurally distinct from dead_code (the guards are reachable, not dead) and from
over_abstraction (the excess is defensive, not structural).

This amendment adds defensive_overengineering as a seventh category, on the record and before
the cases carrying it are built. The category composition target (Section 3) is updated: the
corpus now spans seven categories rather than six. The integrity guarantee is preserved
because this amendment is committed before the defensive_overengineering cases enter the
corpus; the contract on disk describes the corpus at every commit. This addition is disclosed
here rather than applied silently, consistent with the milestone's standard that a changed
methodology is recorded, not hidden.

The three initial defensive_overengineering cases are compute_stats, apply_discount, and clamp.
