# Self-Evolving Code-Optimization Engine: Single-Function Results (30-case authoritative corpus)

_Authoritative single-function dataset, v0.9 P9.5a. Run-and-record only: the frozen corpus was run under one fixed config, with no engine, scoring, gate, build_case, or case change. Every number below traces to `reports/v0.9-dataset.json` (the machine-readable 150-run dataset). No number here comes from a batch report or memory._

## Config and provenance (the fixed run)

- frozen corpus git HEAD: `8b2dd60279c55f251a2ec357ee11dfa561df1359`
- loop config: cap=5, plateau_limit=2, runs_per_case=5
- model: `claude-opus-4-8`, temperature=1.0, max_tokens=8192
- sdk_version: 0.107.1, thinking={adaptive: true, effort: medium}
- corpus: 30 single-function cases run 5 times each = 150 runs (multi-file mcases excluded: doc_history, rate_limiter, task_scheduler)
- transients re-run: 0
- reproducible source: `reports/v0.9-dataset.json` (human-readable companion: `reports/v0.9-dataset.md`)

## Headline finding (Finding 1)

**Across 30 controlled single-function cases run 5 times each (150 runs), optimization is effectively one-shot: 143/150 = 95.3% of runs reached the returned-best candidate in generation 1.** The directed multi-generation loop is verified-present but not load-bearing in the general case at single-function scope. This is the authoritative 30-case confirmation of the one-shot finding (decision 0006), which the earlier 5-case validation set could only suggest.

Global `best_gen` distribution across all 150 runs:

| best_gen | runs |
|---------:|-----:|
| 1 | 143 |
| 2 | 4 |
| 3 | 3 |

`best_gen` is the generation that produced the candidate actually returned. Only 7 of 150 runs (4.7%) returned a candidate first found in generation 2 or 3. The loop's demonstrated value at this scope is verification (the correctness and behavior gates), best-of-N retention, and the never-worse-than-baseline guarantee (decision 0002), not iterative feedback.

## Headline limitation: the corpus is synthetic

**Every case is an authored clean reference degraded by the bloat tool, not real-world code.** This is the headline limitation, stated the way the prior RESULTS.md stated its 5-case size. The claim is about the engine's behavior on controlled degradations of hand-authored functions, not about real-world optimization. A real-world-grade claim needs a corpus drawn from real-world code, which this is not. Both ends of the measured span are synthetic: the 1.0 baseline is the tool-generated bloated original (synthetic ceiling) and the 0.0 floor is the hand-authored reference (synthetic floor). See "Magnitude" below for why magnitude is never the headline here.

## The corpus (30-case roster)

Seven degradation categories (decision: Amendment 1 added `defensive_overengineering` as the seventh). Composition: over_abstraction 6, defensive_overengineering 5, unnecessary_dependency 5, duplication 4, verbose_patterns 4, dead_code 3, excessive_nesting 3. Difficulty: easy 11, medium 12, hard 7. Per-case `best_gen` and `best_cost` distributions are the 5 runs in order.

| case | category | difficulty | best_gen dist | best_cost dist |
|------|----------|------------|---------------|----------------|
| apply_discount | defensive_overengineering | medium | [1, 1, 1, 1, 1] | [-0.0588, -0.0588, -0.0588, -0.0588, -0.0588] |
| apply_shipping | dead_code | easy | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| average | unnecessary_dependency | easy | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| binary_search | dead_code | hard | [1, 1, 1, 1, 1] | [-0.0045, -0.0045, -0.0045, -0.0045, -0.0045] |
| categorize_number | excessive_nesting | easy | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| celsius_to_fahrenheit | over_abstraction | easy | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| chunk | unnecessary_dependency | easy | [1, 1, 1, 1, 1] | [-0.0691, -0.0691, -0.0691, -0.0691, -0.0691] |
| clamp | defensive_overengineering | easy | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| classify_triangle | dead_code | medium | [1, 1, 1, 1, 1] | [-0.0096, 0.0, -0.0129, 0.0, 0.0] |
| compute_stats | defensive_overengineering | hard | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| dedupe | unnecessary_dependency | easy | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| evaluate_postfix | over_abstraction | hard | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| first_or_default | defensive_overengineering | easy | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| format_duration | verbose_patterns | hard | [1, 1, 1, 1, 1] | [0.0037, 0.0, 0.0, 0.0, 0.0] |
| format_phone | verbose_patterns | easy | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| group_by_key | unnecessary_dependency | medium | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| income_tax | duplication | hard | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| int_to_words | excessive_nesting | hard | [1, 2, 2, 1, 1] | [0.004, 0.004, 0.004, 0.004, 0.004] |
| merge_intervals | over_abstraction | medium | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| merge_inventory | duplication | medium | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| min_max | duplication | easy | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| normalize_scores | defensive_overengineering | medium | [1, 1, 1, 1, 1] | [0.0029, 0.0029, 0.0, 0.0029, 0.0029] |
| parse_time | over_abstraction | medium | [1, 1, 1, 1, 1] | [0.0099, 0.0099, 0.0099, 0.0099, 0.0099] |
| parse_version | over_abstraction | medium | [1, 3, 3, 3, 2] | [0.063, 0.0, 0.0, 0.0, 0.0] |
| roman_from_int | over_abstraction | medium | [1, 1, 1, 1, 1] | [0.004, 0.004, 0.004, 0.004, 0.004] |
| roman_to_int | verbose_patterns | medium | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| rps_result | excessive_nesting | medium | [1, 1, 1, 1, 1] | [-0.0036, -0.0036, -0.0036, -0.0036, -0.0036] |
| sum_evens | verbose_patterns | easy | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |
| total_price | duplication | medium | [1, 1, 1, 2, 1] | [0.0107, 0.0107, 0.0107, 0.0, 0.0107] |
| transpose | unnecessary_dependency | hard | [1, 1, 1, 1, 1] | [0.0, 0.0, 0.0, 0.0, 0.0] |

## Finding 2: the loop's role is variance, not shape

On 7 of 150 runs (4.7%), generation 1 fell just short of the floor and the directed loop recovered the returned-best candidate in a later generation. These 7 runs occurred in exactly three cases:

| case | best_gen dist | runs with best_gen > 1 |
|------|---------------|-----------------------:|
| int_to_words | [1, 2, 2, 1, 1] | 2 |
| parse_version | [1, 3, 3, 3, 2] | 4 |
| total_price | [1, 1, 1, 2, 1] | 1 |

**This is run-to-run stochastic recovery near the floor, not a property of function shape or category.** The data states this plainly:

- The same case is one-shot on some runs and loop-recovered on others. `int_to_words` is `[1, 2, 2, 1, 1]` and `total_price` is `[1, 1, 1, 2, 1]`: identical function, identical config, different generation count run to run.
- The three loop-recovery cases do not cluster by category. They span three different categories: `int_to_words` is excessive_nesting, `parse_version` is over_abstraction, `total_price` is duplication.
- A case that looked load-bearing in earlier validation, `parse_time`, was one-shot on all 5 runs here (`best_gen [1, 1, 1, 1, 1]`).

The loop therefore functions as occasional insurance against a generation-1 miss, not as a structural requirement for any identifiable class of function. This report makes **no shape-based or category-based claim** that the loop helps on any kind of function. The generator is a stochastic model at temperature 1.0; on near-floor cases it usually lands on the floor in generation 1 and occasionally lands one step above it, in which case a later generation closes the gap. The never-worse-than-baseline guarantee and best-of-N retention bound the result either way.

## Finding 3: the authored floor is an anchor, not a hard minimum

Five cases produced at least one run with a candidate scored marginally below the 0.0 floor, where the engine found a simpler form than the hand-authored reference:

| case | sub-floor best_cost | runs sub-floor | suspiciously-simple flag |
|------|---------------------|---------------:|--------------------------|
| chunk | -0.0691 | 5 of 5 | yes (all 5) |
| apply_discount | -0.0588 | 5 of 5 | no (see Finding 4) |
| classify_triangle | -0.0096 (run 1), -0.0129 (run 3) | 2 of 5 | yes (the 2 sub-floor runs) |
| binary_search | -0.0045 | 5 of 5 | yes (all 5) |
| rps_result | -0.0036 | 5 of 5 | yes (all 5) |

For the four genuine cases (chunk, binary_search, rps_result, classify_triangle) the candidate is dependency-free and genuinely simpler than the authored reference. These are reported as-is, not corrected. The authored reference is a **0.0 anchor, not a hard minimum**: when a genuinely simpler correct candidate exists, it is scored and returned. There is no objective readability oracle, so the `suspiciously-simple` guard only flags such candidates, it never rejects them (decision 0001). All four genuine sub-floor cases carry the `suspiciously-simple` flag, which is the guard doing exactly its disclosed job: marking the candidate, then returning it.

apply_discount is the fifth sub-floor case and is the exception: it carries no `suspiciously-simple` flag, because it is not simpler. It is the subject of Finding 4.

## Finding 4: a disclosed scorer limitation (the apply_discount case)

apply_discount's sub-floor candidate (`best_cost -0.0588`, identical on all 5 runs) is the hand-authored reference verbatim plus one line, `__all__ = ["apply_discount"]`. That single line is not a structural simplification. It scored below the floor through a non-structural metric trick:

- `dead_code_count`: original 3 -> best 0, floor 1. The `__all__` export marks the lone public function as an explicit export, so the dead-code detector no longer counts it as dead. norm_cost -0.5. This is the **sole** metric scored below the floor, and it alone pulls the weighted cost negative.
- `logical_loc`: original 73 -> best 7, floor 6. The candidate's logical_loc is one **above** the floor, not below it. The +1 is the `__all__` line itself. norm_cost +0.0149.

So the candidate scored lower **without being simpler**: its only below-floor metric is the suppressed dead-code count, while its line count actually rose. The dataset confirms the artifact directly (`confirmed_dead_code_suppression_artifact: true`).

This is stated plainly as a demonstrated limitation of structural-only scoring: a non-structural metric trick can produce a below-floor score without any genuine improvement, and it does so without tripping the `suspiciously-simple` guard (which is why apply_discount, unlike the four genuine sub-floor cases, is unflagged). It is disclosed here as a finding about the scorer, not hidden. This is on-brand for the project's trust-over-capability posture: the scorer's gameability is reported, not buried. Closing it would require a non-structural detector or a process split for the gate; neither is in scope for this run.

## Magnitude (secondary, carries the double-synthetic caveat)

Magnitude is not the headline; `best_gen` is. With that caveat stated, the per-run cost distribution across all 150 runs is:

| best_cost band | runs |
|----------------|-----:|
| below floor (cost < 0) | 22 |
| exactly at floor (cost == 0.0) | 103 |
| above floor (0 < cost) | 25 |

Every one of the 150 runs improved over baseline (`baseline_cost` 1.0 -> `best_cost` near 0.0 on every run) and every run returned a best candidate, never the baseline original. **This magnitude is doubly synthetic and must be read with that caveat.** The 1.0 baseline is a tool-generated bloated original and the 0.0 floor is a hand-authored reference, so "bloat removed" (1 - cost) is measured against a span whose two endpoints are both authored, not observed in real-world code. The honest unit of the headline is the generation count, which does not depend on the synthetic span: 95.3% of runs reach their best in generation 1 regardless of how the span is anchored.

## Cost (from the dataset, for reproducibility)

- total cost: $2.601205 across 150 runs
- mean cost per run: $0.017341
- tokens: 338456 input / 36357 output

These are the real API token counts recorded in `reports/v0.9-dataset.json`.

## Limitations (stated plainly)

- **Synthetic corpus.** Every case is a hand-authored reference degraded by the bloat tool. The results characterize the engine's behavior on controlled degradations, not real-world optimization. This is the headline limitation.
- **Single-function scope.** Every case is one function. At this scope a capable model reaches the structural floor in a single pass on 95.3% of runs, which is why the feedback loop is not load-bearing here. Multi-file results are reported separately.
- **Structural-only scoring is gameable.** Finding 4 demonstrates a non-structural metric trick (the `__all__` dead-code suppression) producing a below-floor score without genuine improvement. Reported, not patched.
- **No objective readability oracle.** The `suspiciously-simple` and `fragmentation-smell` guards flag golfed-but-correct candidates rather than rejecting them, because there is no LLM-free readability oracle and rejecting a genuinely simpler correct answer would violate "objective only" (decision 0001).
- **Behavior-gate in-process forgery is known-open.** The behavior gate runs each candidate inside the locked-down container, which closes the access-based vectors. In-process forgery (the frame-locals serializer hijack and compute-and-lie) stays open and is pinned known-open; closing it needs a process split, deferred by decision 0008. No part of Darwin is described as forgery-proof.

## What these results do NOT claim

- They do **not** claim emergent self-improvement: the generations-used data (95.3% one-shot) does not support it at single-function scope.
- They do **not** make any shape-based or category-based claim about when the loop helps. The 7 loop-recovery runs are run-to-run variance near the floor, spread across three unrelated categories (Finding 2).
- They do **not** credit generation 2 or later with any returned result the data attributes to generation 1 (decision 0006).
- They do **not** present the synthetic corpus as a real-world benchmark, and they do **not** lead with magnitude, whose span is doubly synthetic.
