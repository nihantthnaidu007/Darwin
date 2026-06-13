# Darwin Multi-File (v3) — Validation Results

_Generated 2026-06-13 · model `claude-opus-4-8` · loop config cap=5, plateau=2 · run over the 3 multi-file cases in `mcases/`, each candidate executed inside the v2.0 locked-down container, scored by the post-inverted-span-fix evaluator (decision 0013)._

**This headline rests on SIX runs, not one.** The generator is a stochastic LLM, so a single live run is one sample, not the result. Early single runs landed both "all three cases one-shot" and "all three needed generation 2", which would have supported opposite headlines. The six runs recorded in [`reports/mvariance.json`](mvariance.json) exist to characterize the variance rather than report a coin flip as a finding. Every number below is pulled from that dataset.

## Headline finding

**At multi-file scope, generation 1 removes the bulk of the bloat on every run, but reaching the floor in a single pass is run-dependent.** Generation 1 alone closes roughly 79 to 104 percent of each case's original-to-floor span on every case, every run. When generation 1 falls short, the directed loop **opportunistically** closes the remainder, with high run-to-run variance: the extra ground later generations cover ranges from 0 to about 24 percentage points for the same case across runs. So directed feedback is **not reliably load-bearing** at this scope, but it is **not zero** either. This is distinct from the single-function one-shot finding (decision 0006, where a capable model reached the floor in generation 1 on every improved case) and from the hoped-for payoff of dependable multi-generation feedback.

## The six-run variance

Per case: the generation that produced the returned best across the six runs, how often that was generation 1 (one-shot), and the spread of `feedback_gain_pp` (the percentage points later generations added on top of generation 1). All values from `mvariance.json`.

| case | best generation (6 runs) | one-shot | `feedback_gain_pp` range |
|------|--------------------------|:--------:|:------------------------:|
| `doc_history` | 1, 2, 2, 1, 2, 1 | 3/6 | 0 to 24.02 |
| `rate_limiter` | 1, 2, 3, 2, 2, 3 | 1/6 | 0 to 22.48 |
| `task_scheduler` | 1, 2, 2, 2, 1, 2 | 2/6 | 0 to 10.81 |

The one-shot rate is itself unstable: `doc_history` was one-shot in 3 of 6 runs, `rate_limiter` in 1 of 6, `task_scheduler` in 2 of 6, and **only 1 of the 6 runs had all three cases one-shot at once**. A single run could therefore have reported either "mostly one-shot" or "mostly needs feedback" depending on the draw — which is exactly why one run is not the finding.

## Stable versus noise

**Stable across all six runs:**
- Every run improved all three cases over baseline; the baseline original was never returned; zero regressions across all 18 case-runs.
- Generation 1 alone removes roughly 79 to 104 percent of the original-to-floor span on every case, every run.
- 17 of 18 case-runs returned a best at or below the reference floor (flagged `suspiciously-simple` or `fragmentation-smell`); the one exception is named under soft references below.

**Flips run to run (noise, not finding):**
- One-shot versus needs-generation-2-or-more flips run to run; only 1 of 6 runs had all three cases one-shot.
- `feedback_gain_pp` ranges from 0 to about 24 percentage points for the same case across runs, dominated by where the stochastic generation 1 happened to land.

## Soft references (stated plainly, not buried)

The references in these three cases are **not tight lower bounds.** Across the 18 case-runs, 17 returned a best at or below the reference floor; the one exception — `task_scheduler` run 1, a one-shot run — landed at 98.2 percent of its original-to-floor span, about 1.8 percent above the floor. Because most bests sit at or below the floor, **bloat-removed above 100 percent measures reference looseness, not candidate excellence**: a candidate that scores below the floor has only out-fragmented or out-golfed a reference that was not the true minimum, which is why the engine flags such candidates rather than rewarding them (there is no objective readability oracle). By the same token, the **`feedback_gain_pp` magnitudes are upper bounds, not clean measures of feedback value** — part of the gap a later generation "closes" is slack in a loose reference, not genuine simplification. **Tightening the references is a prerequisite for any benchmark-grade multi-file claim.**

## Scope and honest framing

This is **3 cases, all medium difficulty, over six runs** — a directional validation result, not a conclusion and not a benchmark. Three hand-built multi-file cases exercise the engine end to end; they do not constitute a statistically meaningful population. A benchmark-grade claim needs a larger corpus spread across difficulties and structural patterns. **n=3 is the headline limitation of these results.**

## Relationship to the corrected scorer

These numbers are post the inverted-span fix (decision 0013). Before that fix, a pre-fix run had shown a **spurious `task_scheduler` result**: a generation-2 candidate that regressed an inverted-span metric above the original scored below the floor on that metric, drove a false below-floor weighted cost, and produced a misleading large "feedback did the work" reading. That bug is corrected in the shared evaluator (it affects both single-function and multi-file scoring), and the six runs recorded here were all taken on the corrected scorer. See decision 0013 for the mechanism.

## Limitations (stated plainly)

- **Small corpus.** 3 cases is a validation set, not a benchmark; these numbers establish that the multi-file machinery works end to end, not a population-level claim. Benchmark-grade claims need a larger, difficulty-spread corpus.
- **Medium difficulty only.** All three mcases are medium; the result says nothing about harder, more entangled multi-file units.
- **Soft references.** Most returned bests sit at or below the reference floor, so the references are not tight lower bounds (see above); reported `feedback_gain_pp` magnitudes are therefore upper bounds.
- **Single-run instability.** A single live run is one stochastic sample, and the one-shot / needs-feedback split flips run to run; this is why six runs were taken and the variance is reported rather than a single headline.
- **In-process forgery boundary (carried from v2.0).** Candidates execute inside the locked-down container, which closes the access-based vectors, but the untrusted candidate and the trusted result emitter stay co-resident, so in-process verdict forgery remains open and is pinned known-open (decision 0008, SECURITY.md). It does not bear on these honest-run numbers, but it is carried, not closed.
- **Python only.** The engine, the corpus, and the metric basket are Python-specific.
- **Harness errors rather than rebuilds when the sandbox image is absent.** `mbenchmark` relies on the v2.0 container; with no image built it errors out rather than silently degrading or scoring on the host.

## What these results do NOT claim

- They do **not** claim the directed feedback loop is dependably load-bearing on multi-file as a system property: the magnitude is unstable across runs and inherits the soft-reference looseness, so the loop's contribution is opportunistic, not dependable.
- They are **not** a benchmark: 3 medium cases over six runs are directional, not conclusive.
- They do **not** claim superhuman or near-optimal simplification: bloat-removed above 100 percent reflects a loose reference floor, not a candidate that beat a true minimum.
- They show **no** emergent self-improvement: whether feedback becomes dependable is left open and points to larger scope (more files, more entangled state, harder cases).
