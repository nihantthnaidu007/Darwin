# M0 spike: multi-file behavior equivalence

The research spike that gates v3. Question: can two multi-file units be
objectively verified as behaviorally identical? Findings and the DECISION:
[`reports/M0_EQUIVALENCE.md`](../../reports/M0_EQUIVALENCE.md).

Layout:

- `original/` - the test subject: a stateful TTL+LRU key-value store, 3 modules.
- `variants/preserving/` - 4 behavior-preserving refactors (must be accepted).
- `variants/changing/` - 6 subtle behavior-changing refactors (must be rejected).
- `variants/boundary/` - 1 reworded-error-message strictness probe.
- `variants/adversarial/` - 3 real changes constructed so the check misses them
  (they map the boundary of the guarantee).
- `differ.py` - the differential equivalence check at the public API.
- `run_spike.py` - the full variant matrix with per-class expectations.
- `ablation.py` - scripted-only vs random-only discriminating power.

Run (no Docker, no API key, no LLM; deterministic):

```bash
cd spikes/m0
python run_spike.py   # exit 0 = every expectation held
python ablation.py
```
