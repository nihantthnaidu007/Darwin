# 0017 Run-state checkpointing: append-only JSONL under runs/, resume is opt-in

Decision: The multi-case benchmarks (tools/benchmark.py and tools/mbenchmark.py) persist each case result the moment that case completes, through one shared helper (tools/runstate.py), so a crash mid-corpus never discards finished work. The on-disk format is an append-only JSONL file under runs/ (already gitignored), one record per completed case:

    {"case": "<case id>", "result": <the per-case summary the aggregate is built from>}

The default run is a normal full run that additionally writes this state as it goes; it clears any prior state first so it never silently skips cases from a stale previous run. Resume is a separate opt-in path behind --resume: it reads the prior state, skips the recorded cases, runs only the incomplete ones, and assembles the final aggregate from the union of resumed and newly run results. Only --resume reads prior state.

Context: Closing the continuation half of finding B1. Before this change a crash partway through a corpus run threw away every completed case, even though each case is an independent, already-scored unit. The phase adds state, so the governing constraint is that a complete fresh run produces the byte-identical final aggregate it produced before: the per-case persistence is additive scratch and does not touch the aggregate computation or its output (reports/aggregate.json and reports/maggregate.json keep their shape and content). This phase stays single-threaded and serial; concurrency safety is out of scope (P5.4).

Format properties and the partial-trailing-record rule:
- Human-readable and append-friendly: one self-describing JSON object per line, written with a single append plus flush and fsync.
- Crash-tolerant by construction: json.dumps emits no literal newline (newlines inside strings are escaped), so the only raw newline byte is the record terminator. A record is complete if and only if its line ends in a newline. A crash mid-write leaves a final line with no terminator; the reader stops at it and treats that case as not yet complete, so the case is re-run on resume rather than failing to parse.
- Last write wins: if a case is re-run (for example after a partial write), the later complete record overrides the earlier one, so the resumed result is always the last fully written one.

Alternatives rejected:
- A single end-of-run state dump: defeats the purpose, since a crash before the end loses everything; the requirement is per-case persistence the moment each case completes.
- Atomic whole-file rewrite per case (temp file plus os.replace): more machinery than needed and not append-friendly; the append-only JSONL with the newline-terminator invariant already gives crash tolerance without a rewrite on every case.
- A binary or pickle format: not human-readable and not partial-tolerant, both of which the bar requires.
- Duplicating the persistence logic in each orchestrator: the helper owns the format, the write, the read, and the completed-case detection; the orchestrators call it and never re-implement it, so the two benchmarks cannot drift.

Consequences: The state file lives under runs/ and is gitignored, so it never enters version control and never appears in git diff. Resume assumes the same corpus and the same loop config; after the corpus changes, re-run with a fresh run (the default, which clears prior state), not --resume. Each orchestrator uses its own state file (runs/benchmark_runstate.jsonl and runs/mbenchmark_runstate.jsonl) so the single-function and multi-file runs do not collide. The happy-path equivalence is proven by a test that compares a checkpointed run's aggregate to the non-checkpointed aggregate, not asserted.
