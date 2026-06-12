# 0010 Multi-file case soundness proven by catch-test

Decision: A multi-file case is valid only if its sequence corpus catches every planted break in breaks.py, except breaks marked expect_caught=False, which are documented irreducible misses (M0 gap class 3) and must be missed.

Context: The reference merely passing the corpus proves nothing about corpus strength; a weak corpus passes a weak reference. tools/validate_mcase.py runs the suite, self-equivalence, reference-equivalence, and the catch-test, materializing each break with an exactly-once match assertion and requiring the corpus to flag it non-equivalent. mcases/README.md states a case is valid only if the catch-test passes.

Alternatives rejected:
- Trust reference-equivalence alone: a corpus too weak to catch real breaks would still report the case sound.
- Require every break to be caught with no documented misses: would deny the real M0 boundary (effects not observable through the API).

Consequences: Corpus strength is positively demonstrated, not assumed. The documented expect_caught=False breaks keep the irreducible API-observability boundary explicit and pinned per case.
