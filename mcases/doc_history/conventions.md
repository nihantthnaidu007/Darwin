# doc_history: comparator conventions

- **Exceptions:** exact exception TYPE NAME and exact MESSAGE are
  observable behavior (M0 B1 convention).
- **Equality:** strict typed equality via `mdiffer.canon()`: `True` is not
  `1`. `fields()` order is observable (insertion order, with the documented
  undo-of-remove re-insert-at-end convention). Dict key order is not
  observable (depth()/stats()).
- **Determinism:** no wall clock, no randomness; history is a pure
  function of the call sequence. Both units deterministic by construction.
- **Observables:** per-call return value or exception. The undo/redo
  DEPTHS are observable via depth(); the CONTENT of history entries is not
  exposed by any API and trimmed entries are outside the guarantee (see
  the documented non_observable break).
