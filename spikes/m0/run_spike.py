"""M0 spike runner: every variant through the differential check, with the
expected outcome per variant class. Exit code 0 means every expectation
held (including the adversarial variants being EXPECTED MISSES, which is
the documented gap, not a success of the check).

Run from spikes/m0/:  python run_spike.py
"""

import sys
from pathlib import Path

from differ import build_sequences, check_equivalence

HERE = Path(__file__).parent
ORIGINAL = HERE / "original"

# (label, path, expected_equivalent, note)
VARIANTS = [
    ("self-check original", ORIGINAL, True,
     "sanity: the unit must equal itself"),

    ("P1 renamed/restructured", HERE / "variants/preserving/p1_renamed", True,
     "all internals renamed, bodies re-expressed, new file names"),
    ("P2 merged to one file", HERE / "variants/preserving/p2_merged", True,
     "3 modules merged into a single __init__.py"),
    ("P3 split to five files", HERE / "variants/preserving/p3_split", True,
     "clock and counters extracted into own modules"),
    ("P4 different data structures", HERE / "variants/preserving/p4_datastructs", True,
     "OrderedDict recency, Entry objects"),

    ("C1 capacity off-by-one", HERE / "variants/changing/c1_capacity_off_by_one", False,
     "evicts at > instead of >=; holds capacity+1 entries"),
    ("C2 get() no recency refresh", HERE / "variants/changing/c2_get_no_refresh", False,
     "read path skips recency; later eviction picks a different victim"),
    ("C3 ttl boundary < vs <=", HERE / "variants/changing/c3_ttl_boundary", False,
     "entries survive exactly one tick longer"),
    ("C4 dropped 64-char key cap", HERE / "variants/changing/c4_dropped_validation", False,
     "validation silently accepts long keys"),
    ("C5 put-update no recency refresh", HERE / "variants/changing/c5_update_no_refresh", False,
     "update-in-place skips recency; later eviction differs"),
    ("C6 resize evicts wrong end", HERE / "variants/changing/c6_resize_wrong_end", False,
     "resize evicts MRU instead of LRU"),

    ("B1 reworded error message", HERE / "variants/boundary/b1_reworded_message", False,
     "logic identical; one ValueError message reworded (strictness probe)"),

    ("A1 shadow retention (delete)", HERE / "variants/adversarial/a1_shadow_retention", True,
     "EXPECTED MISS: memory retention is invisible through the API"),
    ("A2 unreached input domain", HERE / "variants/adversarial/a2_unreached_domain", True,
     "EXPECTED MISS: corruption only for keys starting with 'Q'; generator never produces one"),
    ("A3 unreachable deep state", HERE / "variants/adversarial/a3_deep_state", True,
     "EXPECTED MISS: corruption only after 1000 evictions in one lifetime; max here is ~120"),
]


def main():
    sequences = build_sequences()
    n_calls = sum(len(c) + 1 for _, _, c in sequences)
    print(f"sequences: {len(sequences)} ({len(sequences) - 400} scripted + 400 random), "
          f"total calls: {n_calls}, seed fixed\n")

    failures = 0
    for label, path, expect_eq, note in VARIANTS:
        equivalent, witness, info = check_equivalence(ORIGINAL, path, sequences)
        verdict = "EQUIVALENT    " if equivalent else "NOT EQUIVALENT"
        ok = equivalent == expect_eq
        status = "as expected" if ok else "*** UNEXPECTED ***"
        if not ok:
            failures += 1
        print(f"{label:34s} {verdict}  [{status}]")
        print(f"    {note}")
        if witness is not None:
            print(f"    first divergence: seq={witness['sequence']} "
                  f"call#{witness['call_index']} {witness['call']}")
            print(f"      original : {witness['original']}")
            print(f"      candidate: {witness['candidate']}")
        print()

    if failures:
        print(f"RESULT: {failures} variant(s) did not match expectation")
        return 1
    print("RESULT: all expectations held "
          "(adversarial A1-A3 passing the check are the DOCUMENTED GAPS, "
          "not successes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
