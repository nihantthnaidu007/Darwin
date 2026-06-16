# 0018 Structured logging on the core path: console on stderr, JSON fields, result on stdout

Decision: The core path (loop, mloop, generator, mgenerator, evaluator, mevaluator, mverify, benchmark, mbenchmark) emits operational output through the standard-library logging module, configured once in a shared helper (tools/logsetup.py), instead of bare print. The helper installs two handlers on an isolated "darwin" logger: a human-readable console handler on stderr that renders only the message (no level or timestamp prefix, so the aligned progress blocks and tables are not mangled) at a configurable level defaulting to INFO; and an optional structured JSON handler that emits one JSON object per record. Configuration happens only at the entry points (main()), never as an import-time side effect. The RUN SUMMARY report printed by run_summary and mrun_summary stays on stdout via print (it is the program's result, not telemetry), so stdout carries the report and stderr carries the operational log, and the two can be captured separately.

Context: Closing E1. Unattended runs need levels, timestamps, and machine-parseable output, while interactive runs must stay readable. The category boundary is deliberate: only the core path converts; the summary printers (run_summary, mrun_summary) keep their stdout prints, and the one-off developer scripts are out of scope. The values logged are the same values printed before; only the output mechanism changed. The machine artifacts (aggregate.json, maggregate.json, the run-state files) are unchanged.

JSON record envelope (every record):
- timestamp: ISO 8601 UTC, from the record's creation time.
- level: the level name (DEBUG / INFO / WARNING / ERROR).
- logger: the logger name (darwin.loop, darwin.benchmark, darwin.mverify, ...).
- message: the rendered message.

Structured run fields (attached via the logging extra mechanism, so the JSON handler serializes them as top-level fields alongside the envelope):
- loop / mloop run header: case, model, cap, plateau_limit.
- loop / mloop scored generation: generation, verdict, weighted_cost, flags, is_improvement.
- loop / mloop rejected generation: generation, verdict, reason_code, gate.
- loop / mloop final outcome: case, returned, improved_over_baseline, baseline_weighted_cost, best_weighted_cost; and generations, total_input_tokens, total_output_tokens, total_cost_usd, halted; a halt (API failure after the SDK retries) is logged at WARNING with halted.
- benchmark / mbenchmark per case: case, model, verdict, improved_over_baseline, best_generation, bloat_removed_pct, total_cost_usd, total_input_tokens, total_output_tokens; a resumed (skipped) case carries case, resumed.
- benchmark / mbenchmark aggregate header: model, cap, plateau_limit, n_cases; totals line: total_cost_usd, total_input_tokens, total_output_tokens, improved, n_cases.
- evaluator / mevaluator: verdict, reason_code, gate, weighted_cost, flags.
- mverify (the equivalence gate): equivalent, calls_compared, sequences, container_runs; a fail-closed error is logged at WARNING with error.
- mgenerator: model, valid, input_tokens, output_tokens, cost_usd.

Configuration:
- DARWIN_LOG_LEVEL sets the console level (default INFO). Raising it suppresses lower-level records on the console; the JSON handler always records at full fidelity (DEBUG).
- DARWIN_LOG_JSON sets the JSON handler destination; when unset, only the console handler is installed.

Alternatives rejected:
- A logging or metrics backend: out of scope; standard-library logging and json are enough, and a new dependency is disallowed.
- A level/timestamp prefix on the console handler: it would break the aligned progress blocks and tables, against the readability requirement. The timestamp and level live in the JSON record instead.
- Configuring logging at module import: rejected for the same reason the dotenv load was made explicit in P4.1; importing a module must not configure global logging or emit output. The "darwin" logger gets a NullHandler at import and stays isolated from the root logger until an entry point calls configure().
- Converting run_summary / mrun_summary: those print the program's result (the RUN SUMMARY report), which belongs on stdout, not in the operational log.

Consequences: A normal interactive run shows the progress and tables on stderr and the RUN SUMMARY report on stdout, so a pipeline can redirect them apart (for example 2>run.log). Unattended runs set DARWIN_LOG_JSON to capture machine-parseable records. Importing any core-path module configures no global logging and emits nothing. The category-2 summary printers and the category-3 developer scripts are unchanged.
