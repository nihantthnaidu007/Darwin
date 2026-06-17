"""Validate a multi-file case: prove the case is SOUND, not just passing.

Per case, in order:
1. The ORIGINAL passes the case's own test suite (the reference is run
   through the same suite as a bonus parity check).
2. The ORIGINAL is equivalent to ITSELF under the sequence corpus (sanity).
3. The REFERENCE is equivalent to the original under the corpus.
4. THE CATCH-TEST: every planted break in breaks.py is materialized into a
   temp copy of the original and must be CAUGHT by the corpus (flagged
   non-equivalent), except breaks marked expect_caught=False, which are
   documented irreducible boundaries (M0 gap class 3) and must be MISSED.

A break is a patch dict: {name, gap_class, file, old, new, note,
expect_caught} applied to the original with an exactly-once assertion.

Usage (from tools/): python validate_mcase.py <case_name>|--all
Exit 0 only if every step holds for every requested case.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import runinput
from mdiffer import check_equivalence

MCASES = (Path(__file__).parent / ".." / "mcases").resolve()
TOOLS = Path(__file__).parent.resolve()


def _load_module(path):
    # Unique per call with NO shared counter: a uuid is collision-free without
    # coordination, so concurrent loads cannot collide on a sys.modules name
    # (decision 0024). The module is still registered in sys.modules as before.
    name = f"mcase_aux_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_suite(case_dir, unit_name):
    env = dict(os.environ, MCASE_UNIT=unit_name, PYTHONPATH=str(TOOLS))
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "test_suite.py", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=case_dir, env=env, capture_output=True, text=True,
    )
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr.strip()[-120:]
    return proc.returncode == 0, tail


def _materialize_break(original_dir, brk, tmp_root):
    broken = Path(tmp_root) / brk["name"]
    shutil.copytree(original_dir, broken, ignore=shutil.ignore_patterns("__pycache__"))
    target = broken / brk["file"]
    text = target.read_text()
    n = text.count(brk["old"])
    assert n == 1, f"break {brk['name']}: expected exactly 1 match in {brk['file']}, found {n}"
    target.write_text(text.replace(brk["old"], brk["new"]))
    return broken


def _show_witness(witness, indent="        "):
    print(f"{indent}first divergence: seq={witness['sequence']} "
          f"call#{witness['call_index']} {witness['call']}")
    print(f"{indent}  original : {witness['original']}")
    print(f"{indent}  candidate: {witness['candidate']}")


def validate_case(case_name):
    case_dir = MCASES / case_name
    meta = runinput.load_json(case_dir / "meta.json")
    entry = meta["entry"]
    original = case_dir / "original"
    reference = case_dir / "reference"
    corpus = _load_module(case_dir / "corpus.py").build_corpus()
    breaks = _load_module(case_dir / "breaks.py").BREAKS
    n_calls = sum(len(c) + 1 for _, _, c in corpus)
    print(f"=== {case_name} (entry={entry}, corpus: {len(corpus)} sequences, "
          f"{n_calls} calls) ===")
    failures = 0

    for unit in ("original", "reference"):
        ok, tail = _run_suite(case_dir, unit)
        print(f"  [{'PASS' if ok else 'FAIL'}] test suite on {unit}: {tail}")
        failures += 0 if ok else 1

    for label, cand in (("self-equivalence (original vs original)", original),
                        ("reference equivalence (reference vs original)", reference)):
        eq, witness, _ = check_equivalence(original, cand, corpus, entry=entry)
        print(f"  [{'PASS' if eq else 'FAIL'}] {label}: "
              f"{'EQUIVALENT' if eq else 'NOT EQUIVALENT'}")
        if witness:
            _show_witness(witness)
        failures += 0 if eq else 1

    print(f"  catch-test: {len(breaks)} planted breaks")
    with tempfile.TemporaryDirectory() as tmp:
        for brk in breaks:
            broken = _materialize_break(original, brk, tmp)
            eq, witness, _ = check_equivalence(original, broken, corpus, entry=entry)
            expect_caught = brk.get("expect_caught", True)
            if expect_caught:
                ok, verdict = (not eq), ("CAUGHT" if not eq else "MISSED")
            else:
                ok, verdict = eq, ("missed as documented (irreducible: "
                                   + brk["gap_class"] + ")" if eq else
                                   "CAUGHT (was documented as unobservable!)")
            print(f"    [{'PASS' if ok else 'FAIL'}] {brk['name']} "
                  f"[{brk['gap_class']}]: {verdict} - {brk['note']}")
            if witness and expect_caught and not eq:
                _show_witness(witness)
            failures += 0 if ok else 1

    status = "CASE SOUND" if failures == 0 else f"CASE NOT SOUND ({failures} failures)"
    print(f"  -> {status}\n")
    return failures == 0


def _require_pytest(find_spec=importlib.util.find_spec):
    """Fail fast if pytest is not importable in the interpreter running this
    script. Each case suite is run via `python -m pytest` in a subprocess (see
    _run_suite); without pytest that surfaces downstream as a confusing case
    failure rather than a missing dependency. Called at the start of main()."""
    if find_spec("pytest") is None:
        print(
            f"validate_mcase: pytest is not installed in this interpreter "
            f"({sys.executable}). Install requirements: pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)


def main():
    _require_pytest()
    if len(sys.argv) != 2:
        sys.exit("usage: python validate_mcase.py <case_name>|--all")
    names = (sorted(p.name for p in MCASES.iterdir() if (p / "meta.json").exists())
             if sys.argv[1] == "--all" else [sys.argv[1]])
    results = [validate_case(n) for n in names]
    print("ALL CASES SOUND" if all(results) else "VALIDATION FAILURES PRESENT")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
