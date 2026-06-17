# reports/variance_runs

Committed per-run snapshots for the multi-file run-to-run variance study (F1 / P5.3).
Each subdirectory holds one `maggregate.json` (the unmodified output of
`tools/mbenchmark.py --out`), and `tools/variance_harness.py derive` reads every
`maggregate.json` here to regenerate `reports/mvariance.json` from retained artifacts
rather than hand-recorded numbers.

```
reports/variance_runs/
  run_00/maggregate.json
  run_01/maggregate.json
  ...
```

This directory is committable (it is not matched by the `reports/maggregate.json`
gitignore entry, which only ignores the single working-copy aggregate at the reports
root). It is empty of snapshots in P5.3a; the snapshots land in P5.3b.

## Reproduction procedure (two steps)

1. Populate the snapshots. **This runs the model and spends API budget; it is the
   authorized P5.3b step, not run in P5.3a.** From `tools/`:

   ```
   python variance_harness.py run --n 6 --cap 5 --plateau 2 --model claude-opus-4-8
   ```

   This orchestrates six multi-file benchmark runs (each the existing `mbenchmark.py`
   via its `--out`), writing `run_00/ .. run_05/maggregate.json` here, then derives.

2. Regenerate the dataset from the committed snapshots (no spend, deterministic):

   ```
   python variance_harness.py derive
   ```

   `derive` reads the snapshots in a stable order and writes `reports/mvariance.json`;
   re-running it on the same snapshots is byte-identical. Add `--mresults` to also
   print the MRESULTS variance table rows.

Until P5.3b populates this directory, `reports/mvariance.json` carries the 2026-06-13
hand-recorded dataset (see its `note`).
