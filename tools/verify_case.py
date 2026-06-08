"""The gatekeeper. A candidate passes ONLY if its test suite passes AND it
reproduces every golden I/O pair exactly. Either alone is insufficient.

Usage: python verify_case.py <candidate.py> <test_suite.py> <golden_io.json>
Prints "PASS" or "FAIL: <reason>" and exits 0 (pass) / 1 (fail).
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from record_golden import _load, _normalize


def _run_pytest(workdir):
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_suite.py"],
        cwd=workdir, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _replay(candidate_path, golden):
    """Return reason string on first mismatch, else None."""
    fn = getattr(_load(str(candidate_path), "candidate"), golden["entry_point"])
    for case in golden["cases"]:
        actual = _normalize(fn(*case["args"], **case["kwargs"]))
        if actual != case["output"]:
            return (f"golden mismatch for args={case['args']} "
                    f"kwargs={case['kwargs']}: expected {case['output']!r}, "
                    f"got {actual!r}")
    return None


def verify(candidate_path, test_suite_path, golden_path):
    golden = json.load(open(golden_path, encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copy(candidate_path, tmp / "candidate.py")
        shutil.copy(test_suite_path, tmp / "test_suite.py")

        rc, out = _run_pytest(tmp)
        if rc != 0:
            return False, "pytest failed:\n" + out

        mismatch = _replay(tmp / "candidate.py", golden)
        if mismatch:
            return False, mismatch

    return True, "pytest passed and all golden I/O matched"


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: python verify_case.py <candidate.py> <test_suite.py> "
                 "<golden_io.json>")
    ok, reason = verify(*sys.argv[1:4])
    print("PASS" if ok else "FAIL: " + reason)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
