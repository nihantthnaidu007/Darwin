# M0: Can two multi-file units be objectively verified as behaviorally identical?

Research-spike findings. This document is the gate for all of v3. Code:
[`spikes/m0/`](../spikes/m0/). Reproduce with
`cd spikes/m0 && python run_spike.py && python ablation.py` (no Docker, no API
key, no LLM; deterministic, seed fixed).

## DECISION

**Yes: objective multi-file behavior equivalence is achievable at this scope,
via differential testing at the public API, with a guarantee that is real but
strictly weaker than v1's single-function golden I/O.** The check accepted all
4 hand-constructed behavior-preserving refactors (zero false positives) and
rejected all 6 subtle behavior-changing refactors with a concrete first-diverging
call as a witness. Adversarial construction then produced 3 genuine behavior/state
changes the check provably cannot see, which map the boundary of the guarantee
(detailed below). v3 can proceed on this correctness model **only if** it states
the guarantee in its weaker, relative form:

> "No divergence was observed at the public API across N call sequences drawn
> from domain D" rather than v1's "reproduces every recorded golden pair exactly."

The guarantee is relative to (1) the generated call-sequence domain and (2) what
the API exposes. Those two relativities are not removable by more engineering;
they are the shape of the problem once a unit has internal state.

## 1. The question

v1 verifies one pure deterministic function by exact golden input/output replay.
A multi-file unit has internal state, order-dependent behavior, and no single
entry point, so there is no enumerable input space to replay. The spike tested
the closest analogue: treat the unit as a black box with a public API, define
equivalence as "for the same sequence of API calls, identical per-call observable
outputs," and check it differentially against the original.

## 2. The test subject (genuinely stateful, not a pure function in disguise)

[`spikes/m0/original/`](../spikes/m0/original/): a capacity-bounded TTL+LRU
key-value store in 3 modules plus the package init: `store.py` (the `Store`
class, the only public symbol), `recency.py` (LRU bookkeeping), `validation.py`
(argument guards with fixed messages). Public API: `put`, `get`, `peek`,
`delete`, `tick`, `size`, `keys`, `stats`, `resize`.

Why it stresses equivalence rather than dodging it:

- `get()` mutates recency, so which key a later `put()` evicts depends on the
  full access history. No single call has a clean input-to-output contract.
- `peek()` returns exactly what `get()` returns but mutates nothing; sequences
  differing only in get-vs-peek diverge later, not at the call itself.
- `tick()` advances a logical clock and purges expired entries, so behavior
  depends on the interleaving of `put` and `tick`.
- `keys()` reports insertion order while eviction consults recency order: two
  distinct order states live in the unit at once.
- `stats()` exposes cumulative hit/miss/eviction/expiry counters, a digest of
  the entire history.

## 3. The refactor sets (all hand-constructed)

Behavior-preserving (the check must accept):

| variant | what changed |
|---|---|
| P1 `p1_renamed` | every internal renamed, bodies re-expressed, new file names |
| P2 `p2_merged` | 3 modules merged into a single file |
| P3 `p3_split` | split further: clock and counters extracted (5 files) |
| P4 `p4_datastructs` | `OrderedDict` recency, `Entry` objects instead of lists |

Behavior-changing (subtle, the kind an optimization could introduce; the check
must reject):

| variant | the one-line defect |
|---|---|
| C1 | eviction at `>` instead of `>=`: store stably holds capacity+1 entries |
| C2 | `get()` skips the recency refresh ("read path needs no bookkeeping") |
| C3 | expiry at `<` instead of `<=`: entries survive exactly one tick longer |
| C4 | the 64-char key cap silently dropped from validation |
| C5 | `put()` on an existing key skips the recency refresh |
| C6 | `resize()` evicts from the MRU end instead of the LRU end |

Strictness probe: B1 rewords one `ValueError` message, logic untouched.

Adversarial (constructed to be missed; the honest core):

| variant | the change | why the check cannot see it |
|---|---|---|
| A1 | `delete()` retains the value in a shadow dict nothing reads | not observable through any API output, ever |
| A2 | keys starting with `"Q"` store `None` instead of the value | the generator's key domain never produces such a key |
| A3 | after 1000 evictions in one lifetime, `get()` returns `None` | max evictions reachable in a generated sequence is ~120 |

## 4. The check

[`spikes/m0/differ.py`](../spikes/m0/differ.py). 419 sequences: 19 scripted
boundary scenarios (capacity edge, TTL exact boundary, get/peek/update recency
discrimination, resize shrink order, validation probes, constructor probes) plus
400 seeded random sequences (10 to 120 calls each) over a deliberately
collision-heavy domain: 8 keys, capacities 1 to 6 so eviction is constant, TTLs
1 to 5, 4% invalid-argument probes. Every sequence ends with `stats()` and
`keys()` as a full observable-state digest. 27,972 calls compared in total.

Per call, the captured observable is the return value, or the raised exception's
type name and message. Original and candidate each run the sequence on a fresh
instance; outputs are compared with `==`; the verdict is EQUIVALENT or NOT
EQUIVALENT with the first diverging sequence/call as witness. Private internals
are never read.

## 5. Results (raw output of `run_spike.py`)

```
sequences: 419 (19 scripted + 400 random), total calls: 27972, seed fixed

self-check original                EQUIVALENT      [as expected]
P1 renamed/restructured            EQUIVALENT      [as expected]
P2 merged to one file              EQUIVALENT      [as expected]
P3 split to five files             EQUIVALENT      [as expected]
P4 different data structures       EQUIVALENT      [as expected]

C1 capacity off-by-one             NOT EQUIVALENT  [as expected]
    first divergence: seq=overfill_by_one call#5 ('keys', ())
      original : ('ok', ['b', 'c', 'd'])
      candidate: ('ok', ['a', 'b', 'c', 'd'])
C2 get() no recency refresh        NOT EQUIVALENT  [as expected]
    first divergence: seq=get_refresh_then_evict call#5 ('keys', ())
      original : ('ok', ['a', 'c'])
      candidate: ('ok', ['b', 'c'])
C3 ttl boundary < vs <=            NOT EQUIVALENT  [as expected]
    first divergence: seq=ttl_exact_boundary call#4 ('tick', (1,))
      original : ('ok', 1)
      candidate: ('ok', 0)
C4 dropped 64-char key cap         NOT EQUIVALENT  [as expected]
    first divergence: seq=validation_probes call#2 ('put', ('xxx...x[65]', 1))
      original : ('raise', 'ValueError', 'key must be a non-empty string of at most 64 characters')
      candidate: ('ok', None)
C5 put-update no recency refresh   NOT EQUIVALENT  [as expected]
    first divergence: seq=update_refresh_then_evict call#5 ('keys', ())
      original : ('ok', ['a', 'c'])
      candidate: ('ok', ['b', 'c'])
C6 resize evicts wrong end         NOT EQUIVALENT  [as expected]
    first divergence: seq=resize_shrink_order call#8 ('keys', ())
      original : ('ok', ['a', 'b'])
      candidate: ('ok', ['c', 'd'])

B1 reworded error message          NOT EQUIVALENT  [as expected]
    first divergence: seq=validation_probes call#1 ('put', ('', 1))
      original : ('raise', 'ValueError', 'key must be a non-empty string of at most 64 characters')
      candidate: ('raise', 'ValueError', 'key must be a non-empty string (max 64 chars)')

A1 shadow retention (delete)       EQUIVALENT      [as expected]  EXPECTED MISS
A2 unreached input domain          EQUIVALENT      [as expected]  EXPECTED MISS
A3 unreachable deep state          EQUIVALENT      [as expected]  EXPECTED MISS

RESULT: all expectations held
```

False positives: 0 of 4 preserving refactors flagged. Missed changes among the
subtle-but-reachable set: 0 of 6. All three constructed adversarial misses were
confirmed to be real changes by manual witnesses outside the generated domain:
A2 (`get('Qkey')` returns `123` vs `None`), A3 (after 1000 evictions, `1000` vs
`None`), A1 (internal `_graveyard == {'a': 1}` exists; no public method reads it).

Ablation (`ablation.py`): the scripted scenarios alone catch all of C1-C6 and
B1, and the random sequences alone also catch all of them, even at a budget of
only 10 random sequences. The discriminating power for these defects therefore
does not depend on hand-scripted scenario knowledge. The honest caveat: the
random generator's domain itself encodes unit-specific knowledge (a small
colliding key pool, capacities small enough to force eviction, invalid-argument
probes including a 65-char key, which is what exposes C4 without the scripted
probes). Designing that domain per unit is real work that v3 must own.

## 6. The boundary map

What the check provably catches: any behavior difference that manifests as a
different return value or a different exception (type or message) at the public
API, within the generated sequence domain. Empirically that included one-token
comparison-operator defects (C1, C3), state-mutation omissions whose effect
appears only several calls later (C2, C5), dropped validation (C4), and a wrong
eviction end visible only via a rarely-used operation (C6).

What the check provably misses (each demonstrated by construction):

1. **Effects invisible through the API** (A1). Memory retention, timing,
   logging, resource usage. A behavior-equivalence check at the API cannot see
   them by definition. Performance regressions pass as equivalent; for an
   optimizer this class is partially covered elsewhere (structural scoring),
   but it is not a correctness guarantee.
2. **Unreached input subdomains** (A2). The verdict is only as strong as the
   generated argument domain. Anything outside it is unverified.
3. **Unreached deep states** (A3). State reachable only by longer or rarer
   histories than the sequence budget explores is unverified. The input space
   of call sequences is unbounded; coverage is sampled, never exhaustive.

Known strictness and laxity edges of the comparison itself:

- Exception messages are treated as observable behavior (B1 is rejected). This
  is a deliberate convention. Under a looser notion of equivalence B1 would be
  a false positive; v3 must state the convention it adopts.
- Outputs are compared with Python `==`, so a candidate returning `True` where
  the original returns `1` would compare equal. Not observed here; noted as a
  comparator edge.
- The unit under test is deterministic. Nondeterministic units (threads, wall
  clock, hash ordering) would need seams (injected clocks, fixed seeds) before
  this approach applies. The spike's unit got determinism by design via the
  logical clock.

A trust note: the spike ran hand-constructed, trusted variants in-process on the
host. In v3, candidates are untrusted LLM output and must execute across the
v2 container boundary exactly as the v1 gates do; the differential comparison
must stay host-side. The in-process verdict-forgery residual documented in
SECURITY.md carries over unchanged to this check.

## 7. What this means for v3

- The correctness gate for multi-file scope exists and is buildable: golden
  call-sequences at the public API replace golden input/output pairs. Record
  the original's per-call outputs once, replay against candidates.
- The claim language must change. v1 says "behaves identically on every golden
  pair." v3 must say "no divergence observed at the public API over the
  recorded sequence corpus." Strong-but-sampled, and the README must say so.
- Each case needs two new authored artifacts: a public-API definition (what is
  callable, what the argument domains are) and a sequence-generation domain
  tuned to force state collisions (small pools, boundary probes). This is the
  multi-file analogue of v1's golden-I/O recording step, and it is more work
  per case.
- The three gap classes (non-API effects, unreached subdomains, unreached deep
  states) are permanent residents of the threat model, to be documented per
  case, not engineered away.

## 8. Scope confirmation

No multi-file case store was built. No loop integration was built. No LLM
generation was used anywhere; all 14 variants are hand-constructed. Files added
by this spike: 61 Python files under `spikes/m0/` (the unit, 14 variant
packages, `differ.py`, `run_spike.py`, `ablation.py`) plus this document.
Nothing under `tools/`, `cases/`, `seeds/`, or the v1/v2 gates was touched.

## 9. Not done, and the implication

Not done: representativeness beyond one unit (a single 3-file store, one shape
of statefulness); nondeterministic units; side-effecting units (filesystem,
network); sequence-domain authoring as a repeatable recipe rather than a
hand-tuned artifact; running candidates across the container boundary.
Implication: v3's design should treat M0's answer as "the gate is tractable and
its guarantee is sequence-relative and API-relative." The next v3 step is to
design the case format (API spec + sequence domain + recorded golden outcomes)
around exactly that weaker, honestly stated guarantee.
