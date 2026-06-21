# Authoring a new single-function case

This is the user-facing guide to adding a single-function case to the Darwin corpus.
You do not need to read `src/darwin/build_case.py` to follow it: everything the build
command requires of your inputs is documented here, and every example is taken verbatim
from the shipped seed `seeds/roman_to_int/`, which you can open alongside this page.

A case is how the benchmark is extended. You author a clean reference, a test suite, and
a small spec; the build tool degrades the reference into a bloated original and assembles
the finished case. This document specifies exactly what you write.

---

## 1. What you author: the seed directory

Every case starts as a **seed** directory under `seeds/<name>/` holding exactly three
files you write by hand:

```
seeds/roman_to_int/
  reference.py     # the clean, idiomatic function (the 0.0 structural-complexity floor)
  test_suite.py    # the pytest correctness suite (value-returning AND raising behavior)
  spec.json        # the case metadata and the golden value-returning inputs
```

`<name>` is the case id by default (you can override it in `spec.json`, see below). The
build tool reads these three files, never writes back into the seed, and assembles the
finished case under `cases/<case_id>/`.

---

## 2. `spec.json`, field by field

`spec.json` is a single JSON object. Here is the shipped `seeds/roman_to_int/spec.json`,
which this document is verified against:

```json
{
  "category": "verbose_patterns",
  "difficulty": "medium",
  "entry_point": "roman_to_int",
  "description": "Convert a Roman numeral string to its integer value by a single right-to-left pass: add each symbol, subtract it instead when it is smaller than the symbol to its right. Pure and deterministic. Raises ValueError on any non-Roman letter; the empty string is 0. The golden arg_sets cover value-returning inputs only (subtraction pairs, additive runs, compound landmarks, and the empty string); the raising inputs are exercised by the pytest gate in test_suite.py, since the golden recorder captures return values, not exceptions.",
  "arg_sets": [
    ["I"], ["III"], ["IV"], ["IX"], ["VIII"], ["XL"], ["XC"], ["XLII"],
    ["CD"], ["CM"], ["LVIII"], ["MCMXCIV"], ["MMMCMXCIX"], ["MMXXVI"],
    ["DCCCXC"], ["MMMDCCCLXXXVIII"], [""]
  ]
}
```

### `category` (required)

A string naming the degradation pattern the bloated original will carry. It MUST be one
of the **seven** categories. The build tool rejects any other value with
`bad category: <value>`.

| category | what the bloat injects |
|---|---|
| `unnecessary_dependency` | a hand-rolled or imported dependency where the standard library suffices |
| `over_abstraction` | needless indirection, wrappers, classes, or helpers around simple logic |
| `dead_code` | unreachable branches, unused variables, code that runs but does nothing |
| `duplication` | repeated blocks that should be a single loop, helper, or table |
| `excessive_nesting` | deep conditional or loop nesting that flattens cleanly |
| `verbose_patterns` | long-hand patterns where one idiomatic construct does the job |
| `defensive_overengineering` | excess validation: per-element type checks, `try/except` around arithmetic that cannot raise, `None` guards on values that cannot be `None` |

The category is **descriptive metadata**. It is recorded in the finished case's
`meta.json` and used for report grouping; it does **not** enter scoring (the evaluator
never reads it). Pick the one pattern that best describes your case.

### `difficulty` (required)

One of `easy`, `medium`, `hard`. Any other value is rejected with
`bad difficulty: <value>`. This is your judgment of how involved the function is; there
is no mechanical gate beyond the allowed set.

### `entry_point` (required)

The name of the function the corpus exercises. It must be defined in `reference.py`, and
the test suite imports it by this name. In the example the entry point is
`roman_to_int`.

### `description` (required)

Prose describing the public contract: what the function computes, that it is pure and
deterministic, and what it raises and when. This text is part of what the **generator**
sees when it proposes rewrites (the generator is blind to the tests and the golden
outputs), so write the contract clearly. State explicitly which inputs raise and that
those raising inputs live in the test suite, not in `arg_sets` (see the next field for
why).

### `arg_sets` (required)

A JSON list of the **value-returning golden inputs**. During the build the recorder calls
`entry_point(*args, **kwargs)` on each element and freezes the **return value** as the
behavioral oracle (`golden_io.json`). A later candidate is accepted only if it reproduces
every one of these outputs exactly.

Each element is either:

- a **positional list**, for example `["IV"]`, meaning `roman_to_int("IV")`; or
- an **object** `{"args": [...], "kwargs": {...}}` for keyword arguments, for example
  `{"args": [10], "kwargs": {"base": 2}}`.

**Raising inputs do NOT go in `arg_sets`.** The golden recorder captures return values,
not exceptions: if you put a raising input in `arg_sets`, the recorder calls the function
during the build and the exception aborts the build. Exercise raising behavior in
`test_suite.py` with `pytest.raises` instead (see Section 4). The example reflects this:
`arg_sets` carries only value-returning inputs (`"IV"` -> 4, `""` -> 0, and so on), while
`"A"` and `"XIZ"` (which raise `ValueError`) appear only in the test suite.

Choose `arg_sets` to pin the contract: cover the representative and the boundary
value-returning cases so a behavior-wrong candidate cannot slip through. Note that the
golden inputs are deliberately **not** a subset of the test inputs, so a candidate that
memorizes the test assertions is still caught by the golden replay.

### `case_id` (optional)

A string overriding the case id. If omitted, the case id is the seed directory name
(`roman_to_int` here). The finished case is assembled under `cases/<case_id>/`.

---

## 3. `reference.py`: the authoring rules

`reference.py` is the clean function. It defines the **0.0 structural-complexity floor**;
the bloat tool degrades it into the **1.0 anchor** (`original.py`). The reference is the
single largest integrity surface in a case, so it is governed by a fixed rubric
(`docs/darwin-v0.9-corpus-methodology-synthetic.md`, Section 4):

- **Pure and deterministic.** No I/O, no randomness, no global or class state. This is a
  **hard requirement**: the behavior gate is golden-I/O replay, which only works on pure
  functions. The finished case records this as the constraint string
  `deterministic, pure, no I/O, no randomness, no global state`.
- **Standard library only.** No third-party imports. Synthetic cases admit no external
  code.
- **Clean and idiomatic.** The readable form a careful engineer would write: dead code
  removed, redundant control flow collapsed, standard-library constructs used in place of
  hand-rolled equivalents. Optimize for readability, **not** character count. Code-golf is
  disallowed.
- **A clear public contract.** A definite signature, return values, and the exceptions it
  raises on which inputs.
- **Authored to the rubric, NOT to a one-shot target.** Write the reference by the
  structural and readability criteria above, **independently** of what a model can reach
  in a single generation. Never author the reference down to something a one-shot rewrite
  happens to match. This independence is what keeps the project's one-shot finding from
  being an artifact of the floor.

The example `seeds/roman_to_int/reference.py` is a 13-line pure function over a single
literal dictionary, no imports, raising `ValueError` on a non-Roman letter: a clean
representative of `verbose_patterns`.

### Non-triviality (your responsibility)

The bloat tool must have room to inject a substantial original-to-reference span: a case
with no span has nothing to measure. The build tool does **not** gate on span, so this is
an authoring-discipline requirement. Author a non-trivial representative of the category;
do not author a one-liner.

---

## 4. `test_suite.py`: the correctness gate

`test_suite.py` is a normal pytest module. It is run inside the locked-down container
against the candidate code, which is always exposed as the module **`candidate`**, so
import the entry point from there:

```python
import pytest

from candidate import roman_to_int
```

The suite must:

- **Cover the value-returning behavior** that `arg_sets` pins, and any additional
  representative cases. (Golden replay already checks `arg_sets`; the suite is where you
  add structural assertions and intent.)
- **Cover the raising behavior with `pytest.raises`**, since exceptions cannot live in
  `arg_sets`:

```python
def test_invalid_letter_raises():
    with pytest.raises(ValueError):
        roman_to_int("A")
```

The suite must pass on the reference **and** on the bloated original (the build verifies
the original against this suite). Keep it behavior-focused so it does not over-constrain
the structure the optimizer is free to simplify.

---

## 5. Building the case

Once the seed is written, build it from the repository root:

```bash
python -m darwin.build_case seeds/<name>          # build a new case
python -m darwin.build_case seeds/<name> --force  # regenerate an existing, verified case
```

Prerequisites: **Docker** running with the sandbox image built (the verify step runs the
candidate in the container), and **`ANTHROPIC_API_KEY`** set (the bloat step calls the
LLM). From an installed (non-checkout) environment, also set
`DARWIN_DATA_ROOT=/path/to/checkout` so the tool resolves `cases/`.

The build runs in strict order:

1. **Record golden I/O** from `reference.py` over `arg_sets` -> `golden_io.json`.
2. **Bloat** `reference.py` into `original.py` (the LLM degrades it per `category`).
3. **Verify** `original.py` against the test suite AND the golden I/O, inside the
   container.
4. If verification **fails**, the build stops and finalizes nothing (it weakens nothing
   to force a pass).
5. If it **passes**, it freezes baseline metrics, writes `meta.json`, and assembles the
   case under `cases/<case_id>/`.

The build refuses to overwrite an existing verified case unless you pass `--force`. You
can confirm a seed parses (category, difficulty, and entry point are valid) without any
LLM or Docker work by running the command against a seed whose case already exists: it
exits with `REFUSED <case_id>: case <case_id> already exists` before the bloat or verify
steps run.

### What a finished case contains

```
cases/roman_to_int/
  reference.py            # copied from the seed (the floor)
  test_suite.py           # copied from the seed (the correctness gate)
  original.py             # the bloated original (the 1.0 anchor), LLM-generated
  golden_io.json          # the recorded value-returning oracle
  baseline_metrics.json   # frozen structural metrics for original and reference floor
  meta.json               # case_id, category, difficulty, entry_point, description, constraints
```

`meta.json` carries forward exactly the `case_id`, `category`, `difficulty`,
`entry_point`, and `description` from your `spec.json`, plus the fixed `constraints`
string. The `arg_sets` you wrote become `golden_io.json`.

---

## 6. Corpus-integrity rules (so your case strengthens the benchmark)

These follow the methodology contract and keep the corpus outcome-blind:

- **Fix the category composition before building**, not after seeing how Darwin performs.
  The corpus must not be assembled post hoc to flatter a finding.
- **No outcome-based exclusion.** Every case that builds and passes construction stays in
  the corpus, regardless of how Darwin performs on it (baseline returned, one-shot, or
  loop-recovered are all data points).
- **Disclose the synthetic construction.** A case is an authored reference degraded by a
  tool, not real-world code. Both ends of the measured span are synthetic. This is the
  headline limitation and is stated on every results surface.
