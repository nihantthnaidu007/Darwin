"""Assemble one evaluation case from a seed, in strict order:

  (a) record golden I/O from reference.py
  (b) bloat reference.py into original.py (LLM)
  (c) verify original.py against the test suite AND the golden I/O
  (d) if verification FAILS: do not finalize — report and stop (weaken nothing)
  (e) if it PASSES: freeze baseline metrics, write meta.json, assemble the case

A seed dir holds: reference.py, test_suite.py, and spec.json
  { case_id?, category, difficulty, entry_point, description, arg_sets: [...] }

Usage: python build_case.py <seed_dir>
"""
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from bloat import bloat
from freeze_metrics import freeze
from record_golden import record
from verify_case import verify

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"
CONSTRAINTS = "deterministic, pure, no I/O, no randomness, no global state"
CATEGORIES = {
    "unnecessary_dependency", "over_abstraction", "dead_code", "duplication",
    "excessive_nesting", "verbose_patterns", "defensive_overengineering",
}
DIFFICULTIES = {"easy", "medium", "hard"}


def build(seed_dir):
    seed = Path(seed_dir)
    spec = json.load(open(seed / "spec.json", encoding="utf-8"))
    assert spec["category"] in CATEGORIES, f"bad category: {spec['category']}"
    assert spec["difficulty"] in DIFFICULTIES, f"bad difficulty: {spec['difficulty']}"

    reference = seed / "reference.py"
    test_suite = seed / "test_suite.py"
    entry = spec["entry_point"]
    case_id = spec.get("case_id", seed.name)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # (a) record golden from the clean reference
        golden_path = tmp / "golden_io.json"
        golden_path.write_text(
            json.dumps(record(str(reference), entry, spec["arg_sets"]), indent=2) + "\n")

        # (b) bloat the reference into original.py
        original_path = tmp / "original.py"
        original_path.write_text(bloat(str(reference)))

        # (c) gate: pytest AND golden must both pass on original.py
        ok, reason = verify(str(original_path), str(test_suite), str(golden_path))
        if not ok:
            return False, case_id, reason  # (d) stop, finalize nothing

        # (e) freeze metrics, write meta, assemble the case
        baseline = {
            "original": freeze(str(original_path)),
            "reference_floor": freeze(str(reference)),
        }
        meta = {
            "case_id": case_id,
            "category": spec["category"],
            "difficulty": spec["difficulty"],
            "entry_point": entry,
            "description": spec["description"],
            "constraints": CONSTRAINTS,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        case_dir = CASES_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(reference, case_dir / "reference.py")
        shutil.copy(test_suite, case_dir / "test_suite.py")
        shutil.copy(original_path, case_dir / "original.py")
        shutil.copy(golden_path, case_dir / "golden_io.json")
        (case_dir / "baseline_metrics.json").write_text(json.dumps(baseline, indent=2) + "\n")
        (case_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        return True, case_id, reason


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python build_case.py <seed_dir>")
    ok, case_id, reason = build(sys.argv[1])
    if ok:
        print(f"FINALIZED {case_id}: {reason}")
    else:
        print(f"NOT FINALIZED {case_id}: verification failed — {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
