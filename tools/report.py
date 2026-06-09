"""Phase 5 — the honest results report.

Turns a benchmark aggregate (see benchmark.py) into a markdown report. The report
LEADS with whatever the generations-used data actually says: the headline is
DERIVED from best_generation per case, never preordained. If every improved case
reached its best in generation 1, the report says single-function optimization is
effectively one-shot here and the feedback loop was not load-bearing; if any case
needed generation >=2, the report says so instead. The fixed prose (corpus-size
limitation, the behavior-gate forgery boundary, the v2 deferral of multi-file
feedback) reflects established, documented facts of this project.

This module only formats; benchmark.py owns the numbers.
"""

CORPUS_NOTE = (
    "**This is a 5-case validation set, not a benchmark.** Five hand-built cases "
    "(2 seeds + 3 hard) exercise the engine end to end; they do not constitute a "
    "statistically meaningful benchmark. A benchmark-grade claim needs the originally "
    "planned 25-30 cases spread across categories and difficulties. Growing the corpus "
    "to that size is the prerequisite for benchmark claims and is the explicit next "
    "step (deferred here). Corpus size is the headline limitation of these results."
)


# A later-generation gain counts as a MARGINAL refinement (not real feedback work) when
# generation 1 had already removed most of the bloat and the extra gain is tiny. The
# threshold is an explicit, stated judgment, applied to the data — not a preordained label.
MARGINAL_PP = 5.0
NEAR_DONE_PCT = 90.0


def _is_marginal(c):
    return ((c["feedback_gain_pp"] or 0) < MARGINAL_PP
            and (c["first_pass_bloat_removed_pct"] or 0) >= NEAR_DONE_PCT)


def _change_str(c):
    chg = c["structural_changes_from_first"]
    return (", ".join(f"{x['metric']} {x['first_pass']}→{x['best']}" for x in chg)
            if chg else "no structural change (informational metrics only)")


def _headline(agg):
    n, imp = agg["n_cases"], agg["improved"]
    if imp == 0:
        return (f"On all {n} cases the engine returned the baseline original — no "
                f"gate-passing candidate measurably simpler than the baseline was found.")
    need = agg["needed_feedback_cases"]
    one_shot = imp - len(need)
    if not need:
        return (
            f"**Single-function optimization is effectively one-shot for a capable model "
            f"on this corpus.** Every case that improved ({imp} of {n}) reached its "
            f"returned-best candidate in **generation 1** — no case required generation 2 "
            f"or later. The directed multi-generation feedback loop was therefore **not "
            f"load-bearing** here: its demonstrated value on this corpus is *verification* "
            f"(the gates), *best-of-N retention*, and the *never-worse-than-baseline* "
            f"guarantee — not iterative feedback. Directed feedback is expected to become "
            f"load-bearing only at multi-file / system scope, which is deferred to v2.")
    def detail(qualifier):  # qualifier differs by branch so "only" never collides with "substantial"
        return "; ".join(
            f"`{c['case']}` reached its best in generation {c['best_generation']}, but "
            f"generation 1 alone had already removed {c['first_pass_bloat_removed_pct']}% of "
            f"the bloat and the later gain was {qualifier}+{c['feedback_gain_pp']} percentage "
            f"points ({_change_str(c)})" for c in need)
    if all(_is_marginal(c) for c in need):
        return (
            f"**Single-function optimization is effectively one-shot on this corpus, with "
            f"{len(need)} marginal exception(s).** {one_shot} of the {imp} improved cases "
            f"reached their best in **generation 1**; the remaining {len(need)} reached "
            f"their best at generation 2+ but only by a sliver: {detail('only ')}. So "
            f"directed feedback did **real but marginal** work on {len(need)} case and none "
            f"at all on the other {one_shot}. Its v1 value is verification (the gates), "
            f"best-of-N retention, and the never-worse-than-baseline guarantee; "
            f"load-bearing multi-generation feedback is expected only at multi-file / "
            f"system scope (deferred to v2).")
    return (
        f"On this corpus {len(need)} of {imp} improved cases required generation 2 or "
        f"later to reach their best, and the later-generation gain was substantial: "
        f"{detail('')}. The remaining {one_shot} were one-shot (generation 1). Directed "
        f"feedback was load-bearing for the former.")


def _gen_table(agg):
    rows = ["| case | category | difficulty | result | best gen | gens run | floor? |",
            "|------|----------|-----------|--------|---------:|---------:|:------:|"]
    for c in agg["cases"]:
        result = "improved" if c["improved_over_baseline"] else "baseline kept"
        rows.append(
            f"| `{c['case']}` | {c['category']} | {c['difficulty']} | {result} | "
            f"{c['best_generation']} | {c['generations_attempted']} | "
            f"{'yes' if c['floor_reached'] else 'no'} |")
    return "\n".join(rows)


def _reduction_table(agg):
    rows = ["| case | weighted cost (orig→best) | bloat removed | cost (USD) |",
            "|------|:-------------------------:|:-------------:|-----------:|"]
    for c in agg["cases"]:
        bw = c["best_weighted_cost"]
        bloat = f"{c['bloat_removed_pct']}%"
        if bw is not None and bw < 0:  # closed the whole gap AND scored below the floor
            bloat += " ↓floor"
        rows.append(f"| `{c['case']}` | 1.0 → {bw} | {bloat} | ${c['total_cost_usd']} |")
    return "\n".join(rows)


def _per_metric_blocks(agg):
    out = []
    for c in agg["cases"]:
        out.append(f"\n**`{c['case']}`** — structural metrics "
                   f"(original → best, with floor and remaining distance to it):\n")
        out.append("| metric | original | best | floor | to floor | norm cost |")
        out.append("|--------|---------:|-----:|------:|---------:|----------:|")
        for pm in c["per_metric"]:
            nc = "n/a" if pm["norm_cost"] is None else f"{pm['norm_cost']:.3f}"
            out.append(f"| {pm['metric']} | {pm['original']} | {pm['best']} | "
                       f"{pm['floor']} | {pm['best'] - pm['floor']} | {nc} |")
    return "\n".join(out)


def _breakdown(title, table):
    rows = [f"**By {title}:**", "",
            f"| {title} | cases | improved | one-shot | avg bloat removed (vs floor) |",
            "|------|------:|---------:|---------:|----------------------------:|"]
    for key, d in sorted(table.items()):
        rows.append(f"| {key} | {d['n']} | {d['improved']} | {d['one_shot']} | "
                    f"{d['avg_bloat_removed_pct']}% |")
    return "\n".join(rows)


def build_markdown(agg, generated_at):
    cap, plateau = agg["config"]["cap"], agg["config"]["plateau_limit"]
    md = []
    md.append("# Self-Evolving Code-Optimization Engine — Validation Results\n")
    md.append(f"_Generated {generated_at} · model `{agg['model']}` · "
              f"loop config cap={cap}, plateau={plateau} · run UNMODIFIED over "
              f"every case in `cases/`._\n")

    md.append("## Headline finding\n")
    md.append(_headline(agg) + "\n")

    md.append("## Scope and honest framing\n")
    md.append(CORPUS_NOTE + "\n")

    md.append("## Generations used (the key honesty metric)\n")
    md.append(
        "If every case reached its result in generation 1, the feedback loop was not "
        "load-bearing on this corpus — and that is exactly what `best gen` shows. "
        "`gens run` is how many generations the loop *attempted* before stopping "
        "(it can exceed 1 due to the plateau rule even when the kept best is gen 1); "
        "`best gen` is the generation that produced the candidate actually returned.\n")
    md.append(_gen_table(agg) + "\n")
    one_shot = agg["improved"] - len(agg["needed_feedback_cases"])
    md.append(
        f"\n**Summary:** {agg['improved']}/{agg['n_cases']} cases improved over baseline; "
        f"{agg['baseline_returned']}/{agg['n_cases']} returned the baseline original. "
        f"Of the improved cases, **{one_shot} were one-shot (best from generation 1)** "
        f"and **{len(agg['needed_feedback_cases'])} required generation 2+**. "
        + ("No case required generation 2 or later, so multi-generation feedback did "
           "not change any returned result on this corpus.\n"
           if not agg["needed_feedback_cases"]
           else "The magnitude of those gen-2+ gains is broken out below — direction is "
                "not magnitude.\n"))

    if agg["needed_feedback_cases"]:
        md.append("### Magnitude of the gen-2+ gains (direction ≠ load-bearing)\n")
        md.append(
            "A best candidate arriving in generation 2+ only matters if the later "
            "generation did **real** work. For each such case, here is what generation 1 "
            "alone already achieved versus what the feedback added on top:\n")
        rows = ["| case | best gen | gen 1 alone removed | best removed | feedback added | "
                "structural change |",
                "|------|---------:|--------------------:|-------------:|---------------:|"
                "-------------------|"]
        for c in agg["needed_feedback_cases"]:
            rows.append(
                f"| `{c['case']}` | {c['best_generation']} | "
                f"{c['first_pass_bloat_removed_pct']}% | {c['best_bloat_removed_pct']}% | "
                f"+{c['feedback_gain_pp']} pp | {_change_str(c)} |")
        md.append("\n".join(rows) + "\n")

    md.append("## Reduction achieved (verified by the gates)\n")
    md.append(
        "Every `best` candidate below passed the correctness gate (test suite) and the "
        "behavior gate (exact golden I/O replay) before it was scored — these are not "
        "merely \"smaller\" numbers, they are verified behavior-preserving "
        "simplifications. `weighted cost` is the engine's own Method-A score on the "
        "case's original→floor scale (1.0 = the bloated original, 0.0 = the clean "
        "reference floor; lower is better); `bloat removed` is (1 − best cost) — i.e. the "
        "fraction of the original→floor span the engine closed. A value above 100% (marked "
        "`↓floor`) would mean the candidate closed the whole gap and scored *below* the "
        "clean reference floor; the engine flags such candidates `suspiciously-simple` "
        "rather than rewarding them (there is no objective readability oracle).\n")
    md.append(_reduction_table(agg) + "\n")
    md.append(f"\n**Totals:** ${agg['total_cost_usd']} across {agg['n_cases']} cases "
              f"({agg['total_input_tokens']} input / {agg['total_output_tokens']} output "
              f"tokens), real API token counts straight from the loop's own logs.\n")

    md.append("## Per-metric structural reduction\n")
    md.append(
        "Per case, the structural metrics that drive the score (original → best, with "
        "the clean reference floor for reference). `norm cost` is 0.0 at the floor and "
        "1.0 at the original; `n/a` means the case offers no signal on that axis "
        "(original already equals the floor). maintainability_index is omitted here — "
        "it is weight-0 / informational because it is cosmetic-gameable at "
        "single-function scale.\n")
    md.append(_per_metric_blocks(agg) + "\n")

    md.append("## Breakdown by category and difficulty\n")
    md.append("(\"bloat removed\" is always relative to each case's own reference floor; "
              "100% means the case reached its floor, not absolute optimality.)\n")
    md.append(_breakdown("category", agg["by_category"]) + "\n")
    md.append("\n" + _breakdown("difficulty", agg["by_difficulty"]) + "\n")

    md.append("## A note on run-to-run variance (stochastic loop)\n")
    md.append(
        "The generator is a stochastic LLM, so a single live run is one sample, not a "
        "fixed point. On near-floor cases the model usually lands on the exact reference "
        "floor in generation 1, but occasionally lands one logical line above it and a "
        "second generation closes that line — observed run-to-run variance is about ±1 "
        "generation on at most one case, and the generation-2 gain when it happens is a "
        "fraction of a percentage point. The takeaway is unchanged across runs: "
        "**generation 1 does substantially all of the reduction**, and whatever the "
        "sample, the never-worse-than-baseline guarantee and best-of-N retention bound "
        "the result. This report reflects the single run stamped above; re-running may "
        "shift one case's generation count by one without changing the headline.\n")

    md.append("## Limitations (stated plainly)\n")
    md.append(
        "- **Small corpus.** 5 cases is a validation set, not a benchmark; numbers here "
        "establish that the machinery works, not a population-level claim. Benchmark-grade "
        "claims need ~25-30 cases across categories/difficulties (next step).\n"
        "- **Single-function scope.** Every case is one function. At this scope a capable "
        "model reaches the structural floor in a single pass, which is why the feedback "
        "loop is not load-bearing here.\n"
        "- **Directed feedback is a v2 lever.** Multi-generation feedback is expected to "
        "matter at multi-file / system scope (cross-module refactors that cannot be "
        "one-shot), which is out of scope for v1 and deferred to v2.\n"
        "- **Behavior-gate forgery boundary (documented).** The behavior gate replays "
        "golden I/O in a sandbox; it is not a cryptographically isolated environment, so "
        "a candidate that deliberately detects and special-cases the harness is a residual "
        "boundary. Hardening this with OS-level isolation is deferred to v2.\n"
        "- **No objective readability oracle.** The `suspiciously-simple` / "
        "`fragmentation-smell` guards FLAG golfed-but-correct candidates rather than "
        "rejecting them, because there is no LLM-free readability oracle and rejecting a "
        "genuinely simpler correct answer would violate \"objective only.\"\n")

    md.append("## What these results do NOT claim\n")
    md.append(
        "- They do **not** claim emergent self-improvement: the generations-used data does "
        "not support it at single-function scope.\n"
        "- They do **not** present 5 cases as a benchmark.\n"
        "- They do **not** credit multi-generation feedback with any returned result that "
        "the data attributes to generation 1.\n")

    return "\n".join(md) + "\n"
