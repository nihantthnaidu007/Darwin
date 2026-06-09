"""The gatekeeper. A candidate passes ONLY if its test suite passes AND it
reproduces every golden I/O pair exactly. Either alone is insufficient.

The candidate is untrusted LLM output, so BOTH checks run inside the sandbox
(sandbox.py): the test suite and the golden-I/O replay are each executed in an
isolated temp dir under a hard timeout, never imported into this process.

Usage: python verify_case.py <candidate.py> <test_suite.py> <golden_io.json>
Prints "PASS" or "FAIL: <reason>" and exits 0 (pass) / 1 (fail).
"""
import sys
from pathlib import Path

import sandbox

# Replay every golden case against the candidate, in a subprocess. On the first
# mismatch it prints the reason (same wording as the old in-process check) and
# exits 1; it exits 0 only if every case matches.
GOLDEN_DRIVER = '''\
import json
import sys

import candidate

golden = json.load(open("golden_io.json", encoding="utf-8"))
fn = getattr(candidate, golden["entry_point"])
for case in golden["cases"]:
    actual = json.loads(json.dumps(fn(*case["args"], **case["kwargs"])))
    if actual != case["output"]:
        print("golden mismatch for args=%s kwargs=%s: expected %r, got %r"
              % (case["args"], case["kwargs"], case["output"], actual))
        sys.exit(1)
'''


def verify(candidate_path, test_suite_path, golden_path, timeout=10.0):
    candidate_src = Path(candidate_path).read_text(encoding="utf-8")
    test_src = Path(test_suite_path).read_text(encoding="utf-8")
    golden_src = Path(golden_path).read_text(encoding="utf-8")

    pytest_res = sandbox.run(
        {"candidate.py": candidate_src, "test_suite.py": test_src},
        [sys.executable, "-m", "pytest", "-q", "test_suite.py"],
        timeout,
    )
    if pytest_res.status != sandbox.OK:
        # The generic sandbox stays test-agnostic, so it reports a broken-on-import
        # candidate as `failed` (non-zero exit), same as a test-assertion failure.
        # Here, where we KNOW it is pytest, we reconcile: exit code 1 means tests
        # ran and failed; anything else non-OK (collection error 2+, signal crash,
        # timeout) means the candidate could not even run.
        label = ("tests failed" if pytest_res.exit_code == 1
                 else "candidate could not run")
        return False, f"pytest: {label}:\n" + pytest_res.stdout + pytest_res.stderr

    golden_res = sandbox.run(
        {"candidate.py": candidate_src, "golden_io.json": golden_src,
         "driver.py": GOLDEN_DRIVER},
        [sys.executable, "driver.py"],
        timeout,
    )
    if golden_res.status != sandbox.OK:
        reason = (golden_res.stdout.strip() or golden_res.stderr.strip()
                  or f"golden replay {golden_res.status}")
        return False, reason

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
