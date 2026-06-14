# rate_limiter: comparator conventions

- **Exceptions:** exact exception TYPE NAME and exact MESSAGE are
  observable behavior (M0 B1 convention).
- **Equality:** strict typed equality via `mdiffer.canon()`: `True` is not
  `1` (allow() returning 1 instead of True would be non-equivalent). List
  order is observable; dict key order is not.
- **Determinism:** logical clock only (`tick`), no wall time, no
  randomness. Both units are deterministic per sequence by construction.
- **Observables:** per-call return value or exception. Token counts are
  observable only through remaining()/allow(); bucket-internal fields
  (e.g. last_touched) are outside the guarantee where the clamp makes them
  unobservable (see the documented non_observable break).
