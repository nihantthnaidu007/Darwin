"""Tests for the locked-down docker run argv and the opt-in defense-in-depth hook
(P6.4.1, decision 0033).

Tier a (no Docker): the default argv is byte-identical to today when the opt-in is
unset; the opt-in only APPENDS --security-opt entries and removes/alters no lockdown
flag; the env var parses as documented; the module-level opt-in is read at call time.

Tier b (Docker-gated): a SMOKE TEST (not a security validation) that wiring the
example seccomp profile through the opt-in path lets a normal python+pytest candidate
still run. Skips cleanly if the sandbox image is absent.
"""
from pathlib import Path

import pytest

import sandbox_container as scon
from verify_container_sandbox import GOOD, PYTEST_CMD, TEST

REPO = Path(__file__).resolve().parent.parent

# Fixed inputs for the argv tests.
NAME = "darwin_sbx_unit"
WORKDIR = "/host/run"
CMD = ["python", "candidate.py"]

# The EXACT current lockdown argv (P6.1/P6.3-verified), pinned byte-for-byte. Every
# flag here is load-bearing; this list is the contract the opt-in must not disturb.
EXPECTED_DEFAULT_ARGV = [
    "docker", "run",
    "--name", "darwin_sbx_unit",
    "--network", "none",
    "--memory", "256m",
    "--memory-swap", "256m",
    "--cpus", "1.0",
    "--pids-limit", "128",
    "--read-only",
    "--tmpfs", "/tmp:rw,size=64m,mode=1777",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
    "--user", "1000:1000",
    "-v", "/host/run:/sandbox:ro",
    "-w", "/sandbox",
    "-e", "HOME=/tmp",
    "-e", "TMPDIR=/tmp",
    "-e", "PYTHONDONTWRITEBYTECODE=1",
    "-e", "PYTHONPYCACHEPREFIX=/tmp",
    "darwin-sandbox:py313",
    "python", "candidate.py",
]


def _argv(extra_security_opts=None):
    return scon._run_argv(NAME, WORKDIR, CMD, scon.IMAGE, scon.MEMORY, scon.CPUS,
                          scon.PIDS, extra_security_opts=extra_security_opts)


def _strip_pairs(argv, flag, values):
    """Drop every (flag, value) pair from argv where value is in `values`."""
    out, i = [], 0
    while i < len(argv):
        if argv[i] == flag and i + 1 < len(argv) and argv[i + 1] in values:
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return out


# =========================================================== tier a: argv

def test_default_argv_is_byte_identical_when_opt_in_unset():
    """With no opt-in, the produced argv equals the current lockdown argv exactly."""
    assert _argv(extra_security_opts=()) == EXPECTED_DEFAULT_ARGV


def test_opt_in_appends_security_opt_and_preserves_every_lockdown_flag():
    """The opt-in appends additional --security-opt entries; every original lockdown
    flag is still present and unchanged (stripping the extras yields the exact
    default argv -> the extras are purely additive)."""
    extra = ["seccomp=/abs/example-sandbox-seccomp.json", "apparmor=darwin-sandbox"]
    argv = _argv(extra_security_opts=extra)
    for opt in extra:
        assert opt in argv                                   # each extra appears
    assert argv.count("--security-opt") == 1 + len(extra)    # no-new-privileges + the extras
    assert "no-new-privileges" in argv                       # the original security-opt is intact
    # Purely additive: removing the extra pairs reproduces the byte-identical default.
    assert _strip_pairs(argv, "--security-opt", set(extra)) == EXPECTED_DEFAULT_ARGV


def test_env_var_parses_to_extra_opts(monkeypatch):
    """DARWIN_SANDBOX_EXTRA_SECURITY_OPTS parses as a comma-separated, stripped list
    with empties dropped; unset yields the empty (off-by-default) tuple."""
    monkeypatch.setenv(scon._EXTRA_SECURITY_OPTS_ENV, "seccomp=/a.json, apparmor=p ,")
    assert scon._load_extra_security_opts() == ("seccomp=/a.json", "apparmor=p")
    monkeypatch.delenv(scon._EXTRA_SECURITY_OPTS_ENV, raising=False)
    assert scon._load_extra_security_opts() == ()


def test_run_argv_reads_module_level_opt_in_at_call_time(monkeypatch):
    """run() calls _run_argv with no extra arg, so the module-level EXTRA_SECURITY_OPTS
    (populated from the env var at load) is read at call time: set -> appended,
    unset -> byte-identical default."""
    monkeypatch.setattr(scon, "EXTRA_SECURITY_OPTS", ("seccomp=/x.json",))
    argv = _argv(extra_security_opts=None)                   # None -> use the module-level opt-in
    assert "seccomp=/x.json" in argv and argv.count("--security-opt") == 2
    monkeypatch.setattr(scon, "EXTRA_SECURITY_OPTS", ())     # opt-in unset
    assert _argv(extra_security_opts=None) == EXPECTED_DEFAULT_ARGV


# =========================================================== tier b: smoke test (Docker)

def _docker_available():
    # Robust preflight (inspect-by-tag with a docker-image-ls fallback), so the
    # containerd tag-resolution false-negative does not skip this when the image is present.
    try:
        scon._require_image(scon.IMAGE)
        return True
    except (RuntimeError, FileNotFoundError, OSError):
        return False


@pytest.mark.skipif(not _docker_available(),
                    reason=f"Docker sandbox image {scon.IMAGE} not available")
def test_example_seccomp_profile_smoke(monkeypatch):
    """SMOKE TEST, NOT a security validation: wiring the example seccomp profile
    through the opt-in path lets a NORMAL python+pytest candidate still run (the
    profile does not break the normal workload). It does NOT prove the profile blocks
    any attack. Reuses the probe's good-candidate definition rather than inventing one."""
    profile = REPO / "tools" / "seccomp" / "example-sandbox-seccomp.json"
    assert profile.is_file()
    monkeypatch.setattr(scon, "EXTRA_SECURITY_OPTS", (f"seccomp={profile}",))
    res = scon.run({"candidate.py": GOOD, "test_suite.py": TEST}, PYTEST_CMD)
    assert res.status == scon.OK, f"profile broke a normal run: {res.stdout!r} {res.stderr!r}"
