"""Freeze structural metrics for a multi-file case (original + reference).

The v1 basket (freeze_metrics.py) computed per file, aggregated across the
unit: cyclomatic summed/maxed, logical/source LOC summed, nesting maxed,
dependencies unioned (relative in-package imports are excluded by
freeze_metrics' level==0 rule). Dead code is NOT summed per file: vulture
must scavenge the whole unit in one pass, or helpers used from a sibling
file would be falsely flagged. maintainability_index stays per-file only
(weight-0 in v1; no meaningful multi-file aggregate).

Usage (from tools/): python mcase_metrics.py <case_name>
Writes ../mcases/<case>/baseline_metrics.json and prints it.
"""

import json
import sys
from pathlib import Path

from vulture import Vulture

from darwin.freeze_metrics import VULTURE_MIN_CONFIDENCE, freeze


def unit_metrics(unit_dir):
    unit_dir = Path(unit_dir)
    files = sorted(p for p in unit_dir.glob("*.py"))
    per_file = {p.name: freeze(str(p)) for p in files}

    v = Vulture(verbose=False)
    v.scavenge([str(p) for p in files])
    dead = v.get_unused_code(min_confidence=VULTURE_MIN_CONFIDENCE)

    deps = sorted({d for m in per_file.values() for d in m["dependencies"]})
    aggregate = {
        "file_count": len(files),
        "cyclomatic_total": sum(m["cyclomatic_total"] for m in per_file.values()),
        "cyclomatic_max": max(m["cyclomatic_max"] for m in per_file.values()),
        "logical_loc": sum(m["logical_loc"] for m in per_file.values()),
        "source_loc": sum(m["source_loc"] for m in per_file.values()),
        "dependency_count": len(deps),
        "dependencies": deps,
        "dead_code_count": len(dead),
        "max_nesting_depth": max(m["max_nesting_depth"] for m in per_file.values()),
    }
    return {
        "aggregate": aggregate,
        "per_file": {
            name: {
                k: m[k]
                for k in (
                    "cyclomatic_total",
                    "cyclomatic_max",
                    "logical_loc",
                    "source_loc",
                    "max_nesting_depth",
                    "maintainability_index",
                )
            }
            for name, m in per_file.items()
        },
    }


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python mcase_metrics.py <case_name>")
    case_dir = Path("..") / "mcases" / sys.argv[1]
    if not (case_dir / "original").is_dir():
        sys.exit(f"no such case: {case_dir}")
    out = {
        "original": unit_metrics(case_dir / "original"),
        "reference": unit_metrics(case_dir / "reference"),
    }
    (case_dir / "baseline_metrics.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
