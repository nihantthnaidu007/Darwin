"""M0 ablation: where does the check's discriminating power come from?

Runs the changing variants (C1-C6, B1) against three sequence sets:
- scripted boundary scenarios only (19 sequences),
- random sequences only (400 sequences),
- random sequences only, reduced budgets (50 / 10).

If random-only catches everything, the power generalizes without
hand-written scenario knowledge. If only scripted catches something,
the check depends on unit-specific boundary knowledge, which is a real
cost to scale honestly.

Run from spikes/m0/:  python ablation.py
"""

from pathlib import Path

from differ import _random_sequences, _scripted_scenarios, check_equivalence, SEED

HERE = Path(__file__).parent
ORIGINAL = HERE / "original"

CHANGING = [
    ("C1 capacity off-by-one", HERE / "variants/changing/c1_capacity_off_by_one"),
    ("C2 get() no recency refresh", HERE / "variants/changing/c2_get_no_refresh"),
    ("C3 ttl boundary < vs <=", HERE / "variants/changing/c3_ttl_boundary"),
    ("C4 dropped 64-char key cap", HERE / "variants/changing/c4_dropped_validation"),
    ("C5 put-update no recency refresh", HERE / "variants/changing/c5_update_no_refresh"),
    ("C6 resize evicts wrong end", HERE / "variants/changing/c6_resize_wrong_end"),
    ("B1 reworded error message", HERE / "variants/boundary/b1_reworded_message"),
]

SETS = [
    ("scripted only (19)", _scripted_scenarios()),
    ("random only (400)", _random_sequences(400, SEED)),
    ("random only (50)", _random_sequences(50, SEED)),
    ("random only (10)", _random_sequences(10, SEED)),
]


def main():
    header = f"{'variant':36s}" + "".join(f"{name:22s}" for name, _ in SETS)
    print(header)
    for label, path in CHANGING:
        row = f"{label:36s}"
        for _, seqs in SETS:
            equivalent, witness, _ = check_equivalence(ORIGINAL, path, seqs)
            row += f"{'MISSED':22s}" if equivalent else f"{'caught':22s}"
        print(row)


if __name__ == "__main__":
    main()
