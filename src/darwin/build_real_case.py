"""Assemble one evaluation case from a REAL function seed (Path 1), in strict order:

  (a) assert original.py meets the structural-complexity threshold
  (b) verify original.py passes its own test_suite.py (sanity)
  (c) record golden I/O FROM original.py (the real function is the ground truth)
  (d) verify the authored reference.py preserves behavior: it must pass the test
      suite AND replay the golden recorded from the original (the integrity gate)
  (e) freeze baseline metrics from BOTH original.py (the 1.0 anchor) and reference.py
      (the 0.0 floor)
  (f) write meta.json with the provenance block and the measured threshold
  (g) only if every step passes, assemble the case directory

This INVERTS build_case.py. There the clean reference is bloated (by the LLM) into a
synthetic original and the golden is recorded from the reference. Here the real
open-source function IS the original, the clean reference.py is authored by hand, and
the golden is recorded from the ORIGINAL. There is NO bloating in Path 1 -- the model
is never called -- so this module never imports bloat and carries no API dependency.

A seed dir holds: original.py, reference.py, test_suite.py, and spec.json
  { case_id?, category, difficulty, entry_point, description, arg_sets: [...],
    provenance: { source_repo, file, license, commit_or_version } }

The pipeline reuses the existing primitives unchanged: freeze_metrics.freeze,
record_golden.record, and verify_case.verify. Because verify couples the pytest gate
and the golden replay, the step-(b) sanity check is realized by recording the golden
from the original FIRST (step c) and then verifying the original against its suite and
that golden: the golden replay is then tautological, so verify reduces to exactly the
pytest sanity check step (b) intends. The original must still pass its own suite, so
the sanity gate bites; the golden being recorded from the original never weakens it.

Usage: python -m darwin.build_real_case <seed_dir> [--force]
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

from darwin import paths
from darwin import runinput
from darwin.freeze_metrics import freeze
from darwin.record_golden import record
from darwin.verify_case import verify

# The cases directory resolves LAZILY, never at import (the v0.8 invariant, decision
# 0042): the module must import cleanly without a checkout on disk. It resolves at
# first access (inside build or main), not at import; paths.cases_dir() raises a clear
# RuntimeError when no data root is locatable. Same PEP 562 pattern as build_case.py.
_THIS = sys.modules[__name__]


def __getattr__(name):
    if name == "CASES_DIR":
        return paths.cases_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


CONSTRAINTS = "deterministic, pure, no I/O, no randomness, no global state"
CATEGORIES = {
    "unnecessary_dependency",
    "over_abstraction",
    "dead_code",
    "duplication",
    "excessive_nesting",
    "verbose_patterns",
    "defensive_overengineering",
}
DIFFICULTIES = {"easy", "medium", "hard"}

# The structural-complexity threshold (methodology Section 3). Measured on the REAL
# original before any Darwin run. A function below BOTH is too trivial to exercise the
# engine and does not qualify.
THRESHOLD_RULE = "cyclomatic_total >= 6 OR logical_loc >= 20"
MIN_CYCLOMATIC_TOTAL = 6
MIN_LOGICAL_LOC = 20

# The provenance block keys required by the methodology (Section 2): source repository,
# file, license, commit or version. Every key must be present and non-empty.
PROVENANCE_KEYS = ("source_repo", "file", "license", "commit_or_version")

# The SPDX permissive-license allowlist (methodology Section 2). Path 1 admits ONLY
# permissively-licensed real sources, so the recorded license must be one of these
# exact SPDX identifiers. Matching is case-insensitive and whitespace-trimmed; the tool
# does NOT normalize free-form strings (the human records the correct SPDX id when
# sampling -- see "BSD License" is not an id). A copyleft (GPL/AGPL/LGPL) or otherwise
# unrecognized license is rejected before any assembly, so copyleft code can never
# enter the cases/ tree. A future case author reads this constant to know what is admitted.
PERMISSIVE_LICENSES = (
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "ISC",
    "0BSD",
    "Unlicense",
    "Python-2.0",
    "PSF-2.0",
)
_PERMISSIVE_LICENSES_LOWER = frozenset(name.lower() for name in PERMISSIVE_LICENSES)


def _meets_threshold(metrics):
    return (
        metrics["cyclomatic_total"] >= MIN_CYCLOMATIC_TOTAL
        or metrics["logical_loc"] >= MIN_LOGICAL_LOC
    )


def _validate_provenance(spec):
    """Return (ok, reason). The provenance block is mandatory: Path 1 admits only
    permissively-licensed real sources and records per-case provenance, so a seed
    without it cannot be finalized."""
    prov = spec.get("provenance")
    if not isinstance(prov, dict):
        return False, "spec is missing the required 'provenance' block (an object)"
    missing = [k for k in PROVENANCE_KEYS if not str(prov.get(k, "")).strip()]
    if missing:
        keys = ", ".join(repr(k) for k in missing)
        return False, f"provenance block is missing or empty key(s): {keys}"
    # LICENSE ALLOWLIST GATE. The cheapest, most categorical check, so it runs first --
    # before the threshold, sanity, and integrity gates and before any assembly. A
    # non-permissive (copyleft or unrecognized) license can never enter cases/, so it is
    # rejected here, naming the recorded license and the allowlist. Matching is exact on
    # the SPDX id, case-insensitive and whitespace-trimmed; no free-form normalization.
    license_id = str(prov["license"]).strip()
    if license_id.lower() not in _PERMISSIVE_LICENSES_LOWER:
        allow = ", ".join(PERMISSIVE_LICENSES)
        return False, (
            f"license {license_id!r} is not on the permissive allowlist; Path 1 admits "
            f"only permissively-licensed sources (allowed: {allow})"
        )
    return True, None


def build(seed_dir, force=False):
    seed = Path(seed_dir)
    spec = runinput.load_json(seed / "spec.json")
    assert spec["category"] in CATEGORIES, f"bad category: {spec['category']}"
    assert spec["difficulty"] in DIFFICULTIES, f"bad difficulty: {spec['difficulty']}"

    # Provenance is required up front: refuse a seed that cannot be attributed before
    # spending any work assembling it.
    prov_ok, prov_reason = _validate_provenance(spec)
    if not prov_ok:
        return "rejected", spec.get("case_id", seed.name), prov_reason

    original = seed / "original.py"
    reference = seed / "reference.py"
    test_suite = seed / "test_suite.py"
    entry = spec["entry_point"]
    case_id = spec.get("case_id", seed.name)
    case_dir = _THIS.CASES_DIR / case_id

    # Protect a finalized case: refuse to overwrite unless --force is given.
    if case_dir.exists() and not force:
        return (
            "refused",
            case_id,
            (
                f"case {case_id} already exists; pass --force to regenerate, "
                "which will overwrite the finalized case"
            ),
        )
    if case_dir.exists():  # force is True
        print(
            f"WARNING: --force set -- regenerating finalized case {case_id}; files in "
            f"{case_dir} will be overwritten only if the new seed passes every gate."
        )

    # (a) THRESHOLD GATE. Measured on the real original before anything else. Below
    # both thresholds: reject, report, stop -- weaken nothing.
    original_metrics = freeze(str(original))
    if not _meets_threshold(original_metrics):
        return (
            "rejected",
            case_id,
            (
                f"original below complexity threshold ({THRESHOLD_RULE}): measured "
                f"cyclomatic_total={original_metrics['cyclomatic_total']}, "
                f"logical_loc={original_metrics['logical_loc']}"
            ),
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # (c) RECORD GOLDEN FROM ORIGINAL -- the real function is the ground truth.
        # This is the key inversion from build_case.py (which records from reference).
        golden_path = tmp / "golden_io.json"
        golden_path.write_text(
            json.dumps(record(str(original), entry, spec["arg_sets"]), indent=2) + "\n"
        )

        # (b) SANITY GATE. The original must pass its own test suite, so the suite
        # genuinely captures the real function's behavior. verify also replays the
        # golden, which is tautological here (it was recorded from the original), so
        # this reduces to the pytest check on the original. Fail: reject, stop.
        ok, reason = verify(str(original), str(test_suite), str(golden_path))
        if not ok:
            return (
                "rejected",
                case_id,
                f"original.py does not pass its own test suite -- {reason}",
            )

        # (d) INTEGRITY GATE. The authored reference must PRESERVE behavior: pass the
        # test suite AND replay the golden recorded from the original. A reference that
        # changes behavior is rejected here -- the authored floor must be a behavior-
        # preserving cleanup, never a behavior change.
        ok, reason = verify(str(reference), str(test_suite), str(golden_path))
        if not ok:
            return (
                "rejected",
                case_id,
                (
                    "reference.py does not preserve the original's behavior "
                    f"(integrity gate) -- {reason}"
                ),
            )

        # (e) FREEZE BASELINE FROM BOTH: original (the 1.0 anchor) and reference (the
        # 0.0 floor), in the {original, reference_floor} shape the evaluator reads.
        # Reuse the step-(a) freeze of the original rather than recomputing it.
        baseline = {
            "original": original_metrics,
            "reference_floor": freeze(str(reference)),
        }

        # (f) META, including provenance and the record that the threshold was met
        # (the measured cyclomatic_total and logical_loc).
        meta = {
            "case_id": case_id,
            "category": spec["category"],
            "difficulty": spec["difficulty"],
            "entry_point": entry,
            "description": spec["description"],
            "constraints": CONSTRAINTS,
            "provenance": {k: spec["provenance"][k] for k in PROVENANCE_KEYS},
            "threshold": {
                "rule": THRESHOLD_RULE,
                "cyclomatic_total": original_metrics["cyclomatic_total"],
                "logical_loc": original_metrics["logical_loc"],
                "met": True,
            },
        }

        # (g) ASSEMBLE the case directory -- only now that every gate passed.
        case_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(original, case_dir / "original.py")
        shutil.copy(reference, case_dir / "reference.py")
        shutil.copy(test_suite, case_dir / "test_suite.py")
        shutil.copy(golden_path, case_dir / "golden_io.json")
        (case_dir / "baseline_metrics.json").write_text(
            json.dumps(baseline, indent=2) + "\n"
        )
        (case_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        return "finalized", case_id, reason


def main():
    force = "--force" in sys.argv[1:]
    args = [a for a in sys.argv[1:] if a != "--force"]
    if len(args) != 1:
        sys.exit("usage: python -m darwin.build_real_case <seed_dir> [--force]")
    status, case_id, reason = build(args[0], force)
    if status == "finalized":
        print(f"FINALIZED {case_id}: {reason}")
    elif status == "refused":
        print(f"REFUSED {case_id}: {reason}")
        sys.exit(2)
    else:  # rejected
        print(f"NOT FINALIZED {case_id}: {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
