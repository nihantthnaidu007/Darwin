# task_scheduler: comparator conventions

- **Exceptions:** exact exception TYPE NAME and exact MESSAGE are both
  observable behavior. A reworded message is non-equivalent (M0 B1
  convention, carried over).
- **Equality:** strict typed equality via `mdiffer.canon()`: `True` and `1`
  are different observables (closes the `==` laxity M0 documented). Lists
  are order-sensitive; dict KEY ORDER is not observable (stats() dicts
  compare order-insensitively).
- **Determinism:** the unit must be fully deterministic per sequence: no
  wall clock, no randomness, no iteration over sets in observable paths.
  Both units satisfy this by construction (FIFO lists and insertion-ordered
  dicts only).
- **Observables:** per-call return value or exception (type, message).
  `pending()` order and every `stats()` counter are part of behavior.
  Internal job history is NOT exposed by any API and is therefore outside
  the guarantee (see the documented non_observable break).
