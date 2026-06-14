# Self-Evolving Code-Optimization Engine — Validation Results

_Generated 2026-06-13 17:20 UTC · model `claude-opus-4-8` · loop config cap=5, plateau=2 · run UNMODIFIED over every case in `cases/`, each candidate executed inside the I0 locked-down container (v2 OS isolation)._

## Headline finding

**Single-function optimization is effectively one-shot on this corpus, with 2 marginal exception(s).** 3 of the 5 improved cases reached their best in **generation 1**; the remaining 2 reached their best at generation 2+ but only by a sliver: `format_duration` reached its best in generation 2, but generation 1 alone had already removed 99.6% of the bloat and the later gain was only +0.37 percentage points (logical_loc 18→17); `int_to_words` reached its best in generation 2, but generation 1 alone had already removed 99.2% of the bloat and the later gain was only +0.4 percentage points (logical_loc 35→34). So directed feedback did **real but marginal** work on 2 case and none at all on the other 3. Its v1 value is verification (the gates), best-of-N retention, and the never-worse-than-baseline guarantee; load-bearing multi-generation feedback is expected only at multi-file / system scope (deferred to v2).

## Scope and honest framing

**This is a 5-case validation set, not a benchmark.** Five hand-built cases (2 seeds + 3 hard) exercise the engine end to end; they do not constitute a statistically meaningful benchmark. A benchmark-grade claim needs the originally planned 25-30 cases spread across categories and difficulties. Growing the corpus to that size is the prerequisite for benchmark claims and is the explicit next step (deferred here). Corpus size is the headline limitation of these results.

## Generations used (the key honesty metric)

If every case reached its result in generation 1, the feedback loop was not load-bearing on this corpus — and that is exactly what `best gen` shows. `gens run` is how many generations the loop *attempted* before stopping (it can exceed 1 due to the plateau rule even when the kept best is gen 1); `best gen` is the generation that produced the candidate actually returned.

| case | category | difficulty | result | best gen | gens run | floor? |
|------|----------|-----------|--------|---------:|---------:|:------:|
| `format_duration` | verbose_patterns | hard | improved | 2 | 2 | yes |
| `income_tax` | duplication | hard | improved | 1 | 1 | yes |
| `int_to_words` | excessive_nesting | hard | improved | 2 | 4 | no |
| `merge_intervals` | over_abstraction | medium | improved | 1 | 1 | yes |
| `sum_evens` | verbose_patterns | easy | improved | 1 | 1 | yes |


**Summary:** 5/5 cases improved over baseline; 0/5 returned the baseline original. Of the improved cases, **3 were one-shot (best from generation 1)** and **2 required generation 2+**. The magnitude of those gen-2+ gains is broken out below — direction is not magnitude.

### Magnitude of the gen-2+ gains (direction ≠ load-bearing)

A best candidate arriving in generation 2+ only matters if the later generation did **real** work. For each such case, here is what generation 1 alone already achieved versus what the feedback added on top:

| case | best gen | gen 1 alone removed | best removed | feedback added | structural change |
|------|---------:|--------------------:|-------------:|---------------:|-------------------|
| `format_duration` | 2 | 99.6% | 100.0% | +0.37 pp | logical_loc 18→17 |
| `int_to_words` | 2 | 99.2% | 99.6% | +0.4 pp | logical_loc 35→34 |

## Reduction achieved (verified by the gates)

Every `best` candidate below passed the correctness gate (test suite) and the behavior gate (exact golden I/O replay) before it was scored — these are not merely "smaller" numbers, they are verified behavior-preserving simplifications. `weighted cost` is the engine's own Method-A score on the case's original→floor scale (1.0 = the bloated original, 0.0 = the clean reference floor; lower is better); `bloat removed` is (1 − best cost) — i.e. the fraction of the original→floor span the engine closed. A value above 100% (marked `↓floor`) would mean the candidate closed the whole gap and scored *below* the clean reference floor; the engine flags such candidates `suspiciously-simple` rather than rewarding them (there is no objective readability oracle).

| case | weighted cost (orig→best) | bloat removed | cost (USD) |
|------|:-------------------------:|:-------------:|-----------:|
| `format_duration` | 1.0 → 0.0 | 100.0% | $0.034015 |
| `income_tax` | 1.0 → 0.0 | 100.0% | $0.016285 |
| `int_to_words` | 1.0 → 0.004 | 99.6% | $0.104545 |
| `merge_intervals` | 1.0 → 0.0 | 100.0% | $0.00813 |
| `sum_evens` | 1.0 → 0.0 | 100.0% | $0.006145 |


**Totals:** $0.16912 across 5 cases (17709 input / 3223 output tokens), real API token counts straight from the loop's own logs.

## Per-metric structural reduction

Per case, the structural metrics that drive the score (original → best, with the clean reference floor for reference). `norm cost` is 0.0 at the floor and 1.0 at the original; `n/a` means the case offers no signal on that axis (original already equals the floor). maintainability_index is omitted here — it is weight-0 / informational because it is cosmetic-gameable at single-function scale.


**`format_duration`** — structural metrics (original → best, with floor and remaining distance to it):

| metric | original | best | floor | to floor | norm cost |
|--------|---------:|-----:|------:|---------:|----------:|
| cyclomatic_total | 51 | 9 | 9 | 0 | 0.000 |
| logical_loc | 94 | 17 | 17 | 0 | 0.000 |
| max_nesting_depth | 3 | 3 | 3 | 0 | n/a |
| dependency_count | 5 | 0 | 0 | 0 | 0.000 |
| dead_code_count | 9 | 1 | 1 | 0 | 0.000 |
| cyclomatic_max | 4 | 9 | 9 | 0 | n/a |

**`income_tax`** — structural metrics (original → best, with floor and remaining distance to it):

| metric | original | best | floor | to floor | norm cost |
|--------|---------:|-----:|------:|---------:|----------:|
| cyclomatic_total | 37 | 7 | 7 | 0 | 0.000 |
| logical_loc | 72 | 14 | 14 | 0 | 0.000 |
| max_nesting_depth | 3 | 3 | 3 | 0 | n/a |
| dependency_count | 4 | 0 | 0 | 0 | 0.000 |
| dead_code_count | 6 | 1 | 1 | 0 | 0.000 |
| cyclomatic_max | 3 | 7 | 7 | 0 | n/a |

**`int_to_words`** — structural metrics (original → best, with floor and remaining distance to it):

| metric | original | best | floor | to floor | norm cost |
|--------|---------:|-----:|------:|---------:|----------:|
| cyclomatic_total | 42 | 13 | 13 | 0 | 0.000 |
| logical_loc | 104 | 34 | 33 | 1 | 0.014 |
| max_nesting_depth | 3 | 3 | 3 | 0 | n/a |
| dependency_count | 3 | 0 | 0 | 0 | 0.000 |
| dead_code_count | 3 | 0 | 0 | 0 | 0.000 |
| cyclomatic_max | 5 | 8 | 8 | 0 | n/a |

**`merge_intervals`** — structural metrics (original → best, with floor and remaining distance to it):

| metric | original | best | floor | to floor | norm cost |
|--------|---------:|-----:|------:|---------:|----------:|
| cyclomatic_total | 26 | 4 | 4 | 0 | 0.000 |
| logical_loc | 63 | 8 | 8 | 0 | 0.000 |
| max_nesting_depth | 4 | 3 | 3 | 0 | 0.000 |
| dependency_count | 4 | 0 | 0 | 0 | 0.000 |
| dead_code_count | 5 | 1 | 1 | 0 | 0.000 |
| cyclomatic_max | 3 | 4 | 4 | 0 | n/a |

**`sum_evens`** — structural metrics (original → best, with floor and remaining distance to it):

| metric | original | best | floor | to floor | norm cost |
|--------|---------:|-----:|------:|---------:|----------:|
| cyclomatic_total | 25 | 3 | 3 | 0 | 0.000 |
| logical_loc | 56 | 2 | 2 | 0 | 0.000 |
| max_nesting_depth | 3 | 1 | 1 | 0 | 0.000 |
| dependency_count | 5 | 0 | 0 | 0 | 0.000 |
| dead_code_count | 5 | 1 | 1 | 0 | 0.000 |
| cyclomatic_max | 3 | 3 | 3 | 0 | n/a |

## Breakdown by category and difficulty

("bloat removed" is always relative to each case's own reference floor; 100% means the case reached its floor, not absolute optimality.)

**By category:**

| category | cases | improved | one-shot | avg bloat removed (vs floor) |
|------|------:|---------:|---------:|----------------------------:|
| duplication | 1 | 1 | 1 | 100.0% |
| excessive_nesting | 1 | 1 | 0 | 99.6% |
| over_abstraction | 1 | 1 | 1 | 100.0% |
| verbose_patterns | 2 | 2 | 1 | 100.0% |


**By difficulty:**

| difficulty | cases | improved | one-shot | avg bloat removed (vs floor) |
|------|------:|---------:|---------:|----------------------------:|
| easy | 1 | 1 | 1 | 100.0% |
| hard | 3 | 3 | 1 | 99.9% |
| medium | 1 | 1 | 1 | 100.0% |

## A note on run-to-run variance (stochastic loop)

The generator is a stochastic LLM, so a single live run is one sample, not a fixed point. On near-floor cases the model usually lands on the exact reference floor in generation 1, but occasionally lands one logical line above it and a second generation closes that line — observed run-to-run variance is about ±1 generation on at most one case, and the generation-2 gain when it happens is a fraction of a percentage point. The takeaway is unchanged across runs: **generation 1 does substantially all of the reduction**, and whatever the sample, the never-worse-than-baseline guarantee and best-of-N retention bound the result. This report reflects the single run stamped above; re-running may shift one case's generation count by one without changing the headline.

## Limitations (stated plainly)

- **Small corpus.** 5 cases is a validation set, not a benchmark; numbers here establish that the machinery works, not a population-level claim. Benchmark-grade claims need ~25-30 cases across categories/difficulties (next step).
- **Single-function scope.** Every case is one function. At this scope a capable model reaches the structural floor in a single pass, which is why the feedback loop is not load-bearing here.
- **Directed feedback is a v2 lever.** Multi-generation feedback is expected to matter at multi-file / system scope (cross-module refactors that cannot be one-shot), which is out of scope for v1 and deferred to v2.
- **Behavior-gate forgery boundary (v2 — under OS isolation).** Every candidate in these runs executes inside the I0 locked-down container (no network, no host filesystem, memory/CPU/PID caps, non-root). That OS boundary CLOSES the access-based vectors: oracle-read (the golden file is not in the container), host-filesystem/secret reads, network, and the literal `import __main__` serializer-attribute form. It does NOT split the process, so the untrusted candidate and the trusted result emitter stay co-resident; in-process forgery (the frame-locals serializer hijack and compute-and-lie) is therefore still OPEN and is pinned, known-open, in `tools/test_behavior_gate_limits.py`. Closing it needs a process split (architecture change), deferred by decision — not patched here.
- **No objective readability oracle.** The `suspiciously-simple` / `fragmentation-smell` guards FLAG golfed-but-correct candidates rather than rejecting them, because there is no LLM-free readability oracle and rejecting a genuinely simpler correct answer would violate "objective only."

## What these results do NOT claim

- They do **not** claim emergent self-improvement: the generations-used data does not support it at single-function scope.
- They do **not** present 5 cases as a benchmark.
- They do **not** credit multi-generation feedback with any returned result that the data attributes to generation 1.

