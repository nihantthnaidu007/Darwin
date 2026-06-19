"""Proof-by-execution for the Phase I0 container sandbox primitive.

Runs the container sandbox (sandbox_container.py) against a battery of candidates,
including the adversarial ones, and checks each guarantee with raw output:
  a good -> ok            f timeout (never hang) -> timed_out, container gone
  b fail -> failed        g memory flood -> killed by the cap (oom)
  c crash -> crashed      h fork bomb -> contained by the PID cap, call returns
  d network blocked       i always clean up -> no leaked containers or host dirs
  e host filesystem blocked

Exit 0 = every guarantee held; exit 1 = a guarantee broke.
Usage (Docker must be running, image built):  python verify_container_sandbox.py
"""

import glob
import os
import subprocess
import tempfile
from pathlib import Path

from darwin import paths
from darwin import sandbox_container as scon


REPO = paths.data_root()
HOST_ENV = REPO / ".env"  # a real host secret; the container must NOT reach it

PASS, FAIL = "PASS", "FAIL"
_results: list[tuple[str, bool]] = []


def check(label, ok, evidence):
    _results.append((label, ok))
    print("=" * 78)
    print(f"[{PASS if ok else FAIL}] {label}")
    print("-" * 78)
    print(evidence.rstrip())
    print()


def show(res):
    return (
        f"status={res.status} exit_code={res.exit_code} "
        f"timed_out={res.timed_out} oom_killed={res.oom_killed} "
        f"duration={res.duration:.2f}s\n"
        f"stdout: {res.stdout.strip()!r}\n"
        f"stderr: {res.stderr.strip()[:400]!r}"
    )


def stray_containers():
    """Names of any containers this primitive created that still exist."""
    p = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "name=darwin_sbx_",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return [n for n in p.stdout.splitlines() if n.strip()]


def stray_hostdirs():
    """Any leftover per-run host temp dirs / output files from this primitive."""
    base = tempfile.gettempdir()
    return sorted(glob.glob(os.path.join(base, "darwin_sbx_*")))


# --- candidates -------------------------------------------------------------
GOOD = "def sum_evens(xs):\n    return sum(x for x in xs if x % 2 == 0)\n"
BAD = "def sum_evens(xs):\n    return 999  # wrong on purpose\n"
TEST = (
    "from candidate import sum_evens\n\n"
    "def test_basic():\n    assert sum_evens([1, 2, 3, 4]) == 6\n"
)
PYTEST_CMD = ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_suite.py"]

CRASH = "import os\nos.abort()\n"  # SIGABRT -> 128+6 = 134
LOOP = "while True:\n    pass\n"
FLOOD = (
    "chunks = []\n"
    "while True:\n"
    "    chunks.append(bytearray(10 * 1024 * 1024))  # 10 MB at a time\n"
)
FORKBOMB = (
    "import os, time\n"
    "n = 0\n"
    "try:\n"
    "    while True:\n"
    "        pid = os.fork()\n"
    "        if pid == 0:\n"
    "            time.sleep(60)\n"  # child idles, holding a PID slot
    "            os._exit(0)\n"
    "        n += 1\n"
    "except OSError as e:\n"
    # os.write to fd 1 is unbuffered: it survives os._exit (print's buffer would not)
    "    os.write(1, ('fork blocked after %d children: %s\\n'\n"
    "                 % (n, e.__class__.__name__)).encode())\n"
    "os._exit(0)\n"
)
NETWORK = (
    "import socket, json\n"
    "r = {}\n"
    "try:\n"
    "    s = socket.create_connection(('1.1.1.1', 53), timeout=3); s.close()\n"
    "    r['tcp'] = 'REACHED (BAD)'\n"
    "except OSError as e:\n"
    "    r['tcp'] = 'blocked -> ' + e.__class__.__name__\n"
    "try:\n"
    "    socket.gethostbyname('example.com'); r['dns'] = 'RESOLVED (BAD)'\n"
    "except OSError as e:\n"
    "    r['dns'] = 'blocked -> ' + e.__class__.__name__\n"
    "print(json.dumps(r))\n"
)
HOSTFS = (
    "import os, json\n"
    f"host_env = {str(HOST_ENV)!r}\n"
    "r = {}\n"
    "try:\n"
    "    data = open(host_env).read(); r['host_env'] = 'READABLE (BAD): ' + data[:20]\n"
    "except OSError as e:\n"
    "    r['host_env'] = 'unreachable -> ' + e.__class__.__name__\n"
    "r['sandbox_listing'] = sorted(os.listdir('/sandbox'))\n"
    "r['root_listing'] = sorted(os.listdir('/'))\n"
    "print(json.dumps(r))\n"
)


def main():
    print("lockdown argv (one flag per item):")
    argv = scon._run_argv(
        "darwin_sbx_demo",
        Path("/host/run"),
        ["python", "x.py"],
        scon.IMAGE,
        scon.MEMORY,
        scon.CPUS,
        scon.PIDS,
    )
    print("  " + " ".join(argv))
    print(f"\nstray containers before: {stray_containers()}")
    print(f"stray host dirs before:  {stray_hostdirs()}\n")

    # a. good candidate -> ok (also exercises pytest inside the image)
    r = scon.run({"candidate.py": GOOD, "test_suite.py": TEST}, PYTEST_CMD)
    check("a. good candidate -> status=ok", r.status == scon.OK, show(r))

    # b. failing candidate -> failed (pytest assertion fails, exit 1)
    r = scon.run({"candidate.py": BAD, "test_suite.py": TEST}, PYTEST_CMD)
    check(
        "b. failing candidate -> status=failed",
        r.status == scon.FAILED and "failed" in r.stdout.lower(),
        show(r),
    )

    # c. crashing candidate -> crashed (SIGABRT, returns normally)
    r = scon.run({"candidate.py": CRASH}, ["python", "candidate.py"])
    check(
        "c. crashing candidate -> status=crashed (sandbox returns normally)",
        r.status == scon.CRASHED,
        show(r),
    )

    # d. network blocked
    r = scon.run({"candidate.py": NETWORK}, ["python", "candidate.py"])
    check(
        "d. NETWORK BLOCKED (--network none holds)",
        "blocked" in r.stdout
        and "REACHED" not in r.stdout
        and "RESOLVED" not in r.stdout,
        show(r),
    )

    # e. host filesystem blocked
    r = scon.run({"candidate.py": HOSTFS}, ["python", "candidate.py"])
    e_ok = (
        "unreachable" in r.stdout
        and "READABLE" not in r.stdout
        and '"sandbox_listing": ["candidate.py"]' in r.stdout.replace("'", '"')
    )
    check(
        "e. HOST FILESYSTEM BLOCKED (sees only its own code; host .env unreachable)",
        e_ok,
        show(r),
    )

    # f. timeout -> never hang; container gone afterward
    r = scon.run({"candidate.py": LOOP}, ["python", "candidate.py"], timeout=3.0)
    after = stray_containers()
    f_ok = (
        r.status == scon.TIMED_OUT
        and r.timed_out
        and r.duration < 3.0 + scon._STARTUP_GRACE + scon._KILL_GRACE
        and after == []
    )
    check(
        "f. TIMEOUT (never hang): killed ~timeout, returns, container gone",
        f_ok,
        show(r) + f"\ncontainers named darwin_sbx_ after run: {after}",
    )

    # g. memory flood -> killed by the cap
    r = scon.run({"candidate.py": FLOOD}, ["python", "candidate.py"], timeout=15.0)
    check(
        "g. MEMORY LIMIT: flooder killed by the cap (closes v1 output-RAM risk)",
        r.oom_killed and r.status == scon.CRASHED,
        show(r),
    )

    # h. fork bomb -> contained by the PID cap; call still returns
    r = scon.run({"candidate.py": FORKBOMB}, ["python", "candidate.py"], timeout=15.0)
    h_ok = "fork blocked after" in r.stdout
    check(
        "h. PID/fork limit: fork bomb contained by --pids-limit; call returns",
        h_ok,
        show(r),
    )

    # i. always clean up: nothing leaked after success/timeout/crash above
    c, d = stray_containers(), stray_hostdirs()
    check(
        "i. ALWAYS CLEAN UP: no leaked containers, no leaked host temp artifacts",
        c == [] and d == [],
        f"stray containers after all runs: {c}\nstray host dirs after all runs: {d}",
    )

    print("=" * 78)
    failed = [lbl for lbl, ok in _results if not ok]
    if failed:
        print(f"RESULT: {len(failed)} FAILED -> {failed}")
        raise SystemExit(1)
    print(f"RESULT: all {len(_results)} guarantees held.")


if __name__ == "__main__":
    main()
