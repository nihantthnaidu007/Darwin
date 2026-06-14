# 0004 Maintainability index removed from scoring

Decision: maintainability_index is given weight 0 in the score. It is still measured and logged for human observability, never scored.

Context: An independent audit showed radon maintainability index is gameable by cosmetics at single-function scale. Adding a docstring or comments or lengthening variable names raises it with no real complexity removed; on income_tax a padded copy of the reference scored below the clean floor. tools/evaluator.py WEIGHTS sets it to 0.0 with the rationale inline.

Alternatives rejected:
- Keep maintainability index weighted: cosmetic padding would register as improvement.
- Drop it from the basket entirely: loses an informational signal humans may still want.

Consequences: The structural metrics that carry the score (cyclomatic totals, logical LOC, nesting, dependencies, dead code) are not movable by a docstring. Cosmetic padding cannot score as a win.
