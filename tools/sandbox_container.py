"""A container-isolated code sandbox: run a command against a set of files inside
a LOCKED-DOWN Docker container, under a hard wall-clock timeout, and report what
happened. This is the Phase I0 boundary upgrade of sandbox.py — a real OS boundary
(a container) instead of a process-group boundary — keeping every Phase 1 guarantee.

Same contract as sandbox.py, on purpose, so I1 can adopt it: write `files`
(name -> text) into a fresh dir, run `command` there, return a structured result
with status (ok / failed / crashed / timed_out), exit code, stdout, stderr, and
duration. It knows nothing about "tests" or "golden I/O"; that lives one layer up.

THE THREE GUARANTEES (inherited from Phase 1, now at the container level):
  * NEVER HANG. The call always returns within ~timeout (+ a bounded startup/
    teardown grace), no matter what the candidate does (infinite loop, fork bomb,
    flooding stdout). Docker has no "run for at most N seconds" flag, so the wall
    clock is enforced here: `docker run` is launched with a bounded wait and, on
    expiry, the whole container is force-removed in the daemon (`docker rm -f`).
    Unlike sandbox.py the untrusted processes are NOT our children — they live in
    the daemon — so the Phase 1 "breakaway child holding our stdout pipe" hazard
    cannot occur: we never share a pipe with them. Container output is written to
    host temp FILES and read back capped, so even an endless `print` flood can
    neither deadlock us nor grow host RAM without bound.
  * ALWAYS CLEAN UP. A `finally` always runs `docker rm -f` (idempotent) and
    removes the host temp dir and the output files. No leaked container is the
    new "no leaked temp dir": a container that is not torn down is as unacceptable
    as a hung one. Every docker subcommand is itself time-bounded so a wedged
    daemon cannot make teardown hang.
  * STRUCTURED RESULT. ContainerResult mirrors sandbox.SandboxResult field-for-
    field (status / exit_code / stdout / stderr / duration / timed_out) and adds
    one container fact: oom_killed (killed by the memory cap).

THE LOCKDOWN (each item independently verifiable; see verify_container_sandbox.py):
  no network (--network none); no host filesystem beyond a single read-only
  bind-mount of the per-run dir at /sandbox; memory cap with swap disabled
  (--memory == --memory-swap); CPU cap (--cpus); PID cap (--pids-limit, contains
  fork bombs); non-root inside (image USER + --user 1000); read-only root
  filesystem with a writable in-RAM tmpfs at /tmp only; dropped capabilities and
  no-new-privileges; hard wall-clock timeout enforced here.

PREREQUISITE: Docker must be installed and running on the host, and the sandbox
image must be built once:
    docker build -f tools/Dockerfile.sandbox -t darwin-sandbox:py313 tools/
run() raises RuntimeError with this hint if the image is missing.

SCOPE: this is the primitive only. Wiring the evaluator across the boundary is I1.
"""
import os
import shutil
import stat
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

# The four-way outcome, identical to sandbox.py so the taxonomy is shared. OOM is
# reported separately (oom_killed) and mapped to CRASHED here: a candidate killed
# by the memory cap was terminated abnormally, like a signal death.
OK = "ok"                # completed successfully (exit 0)
FAILED = "failed"        # completed with a non-zero exit code
CRASHED = "crashed"      # terminated abnormally (signal, or killed by the memory cap)
TIMED_OUT = "timed_out"  # killed by the sandbox's wall-clock timeout

IMAGE = "darwin-sandbox:py313"  # built from tools/Dockerfile.sandbox

# Default container caps. Generous enough for a pytest run on the tiny cases,
# tight enough to contain a hostile candidate.
MEMORY = "256m"   # RAM cap; swap is disabled by setting --memory-swap == --memory
CPUS = "1.0"      # at most one core
PIDS = 128        # process cap; contains fork bombs

# Bound the host-side waits so nothing can hang us. The container's wall clock is
# `timeout`; _STARTUP_GRACE covers image-start latency (measured ~0.1-0.4s warm, so
# 1.0s is a wide margin) so a slow-starting legit candidate is not killed early.
# Idle docker subcommands (inspect/rm) get _OP_TIMEOUT; the post-kill reap of the
# docker client gets _KILL_GRACE. None of these can block longer than shown.
_STARTUP_GRACE = 1.0
_OP_TIMEOUT = 15.0
_KILL_GRACE = 5.0

# Cap how much output we read back from the container (per stream), bounding host
# memory even if the candidate floods stdout. The container memory cap stops an
# in-RAM flood; this stops a streaming-print flood. Closes v1's deferred risk.
_MAX_OUTPUT = 1_000_000  # bytes per stream

# OPT-IN defense-in-depth, OFF BY DEFAULT (P6.4.1, decision 0033). The 1.0 default is
# single-user-trusted, so the default lockdown is the floor and this adds nothing
# unless an operator turns it on. DARWIN_SANDBOX_EXTRA_SECURITY_OPTS is a comma-
# separated list of docker --security-opt values (for example
# "seccomp=/abs/path/example-sandbox-seccomp.json", optionally also "apparmor=...");
# each becomes an ADDITIONAL --security-opt on top of the lockdown -- it never removes
# or alters a lockdown flag (opt-in only ADDS restriction). Read ONCE here at module
# load, mirroring the operator-side DARWIN_LOG_* convention in logsetup: this is
# deployment configuration, not a per-call argument, so a multi-tenant operator hardens
# the deployment without editing code. Unset -> empty -> the produced argv is byte-
# identical to today (TASK CONSTRAINT 1). Values containing a comma (some SELinux
# label opts) are not expressible here by design; the common seccomp/apparmor case is.
_EXTRA_SECURITY_OPTS_ENV = "DARWIN_SANDBOX_EXTRA_SECURITY_OPTS"


def _load_extra_security_opts():
    raw = os.environ.get(_EXTRA_SECURITY_OPTS_ENV, "")
    return tuple(opt.strip() for opt in raw.split(",") if opt.strip())


EXTRA_SECURITY_OPTS = _load_extra_security_opts()


@dataclass
class ContainerResult:
    status: str            # one of OK / FAILED / CRASHED / TIMED_OUT
    exit_code: int | None  # container exit code; None when timed out
    stdout: str            # captured standard output (capped at _MAX_OUTPUT)
    stderr: str            # captured standard error (capped at _MAX_OUTPUT)
    duration: float        # wall-clock seconds the container actually ran
    timed_out: bool        # convenience flag, == (status == TIMED_OUT)
    oom_killed: bool       # True if the container was killed by the memory cap


def run(files, command, timeout=10.0, image=IMAGE,
        memory=MEMORY, cpus=CPUS, pids=PIDS):
    """Write `files` (name -> text) into a fresh host temp dir, run `command` in a
    locked-down container with that dir read-only-mounted at /sandbox, and return a
    ContainerResult. Enforces a hard `timeout` in seconds: on expiry the container
    is force-removed and the result is marked timed out. The call always returns
    within ~timeout + a bounded grace, and the container and host temp artifacts are
    always removed before returning, even on timeout or crash.
    """
    _require_image(image)
    name = "darwin_sbx_" + uuid.uuid4().hex  # unique; the teardown handle
    # Output goes to host files OUTSIDE the mounted dir (the container never sees
    # them), so a full pipe can never deadlock us and we read back only a capped
    # amount. Created on the host, owned by us, not by the container user.
    out_fd, out_path = tempfile.mkstemp(prefix="darwin_sbx_out_")
    err_fd, err_path = tempfile.mkstemp(prefix="darwin_sbx_err_")
    os.close(out_fd)
    os.close(err_fd)
    workdir = None
    try:
        workdir = _stage(files)
        argv = _run_argv(name, workdir, command, image, memory, cpus, pids)
        start = time.monotonic()
        with open(out_path, "wb") as out_f, open(err_path, "wb") as err_f:
            # No --rm: keep the container after exit so we can inspect OOM/exit;
            # the finally below force-removes it on every path.
            proc = subprocess.Popen(argv, stdout=out_f, stderr=err_f,
                                    start_new_session=True)
            timed_out = False
            try:
                proc.communicate(timeout=timeout + _STARTUP_GRACE)
            except subprocess.TimeoutExpired:
                timed_out = True
                # Authoritatively stop the runaway IN THE DAEMON (killing the local
                # `docker run` client would not stop the container). This also
                # detaches the client so its wait returns.
                _docker(["rm", "-f", name])
                try:
                    proc.wait(timeout=_KILL_GRACE)
                except subprocess.TimeoutExpired:
                    proc.kill()  # reap the docker client itself; never block
                    try:
                        proc.wait(timeout=_KILL_GRACE)
                    except subprocess.TimeoutExpired:
                        pass
        duration = time.monotonic() - start
        stdout = _read_capped(out_path, _MAX_OUTPUT)
        stderr = _read_capped(err_path, _MAX_OUTPUT)

        if timed_out:
            return ContainerResult(TIMED_OUT, None, stdout, stderr,
                                   duration, True, False)

        # Not timed out: the container exists (no --rm), so inspect is authoritative
        # for the exit code and the OOM flag. Fall back to the client's returncode
        # if inspect cannot read it (e.g. the container never started).
        exit_code, oom = _inspect(name)
        if exit_code is None:
            exit_code = proc.returncode
        status = _classify(exit_code, oom)
        return ContainerResult(status, exit_code, stdout, stderr,
                               duration, False, oom)
    finally:
        # Guaranteed teardown on every path (success, failure, crash, timeout).
        # Idempotent: a "No such container" from an already-removed container is
        # fine. Bounded so a wedged daemon cannot hang cleanup.
        _docker(["rm", "-f", name])
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)
        for p in (out_path, err_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def _stage(files):
    """Write `files` (name -> text) into a fresh host temp dir and return its Path.

    mkdtemp creates the dir mode 0o700 by design. On a Linux Docker host a
    read-only bind mount preserves the host directory's owner and mode, so the
    container's uid 1000 (a different uid than ours) cannot traverse or read a
    0o700 dir we own: every run fails with "Permission denied: /sandbox/driver.py".
    We widen the staged tree so a non-owner uid can traverse and read it -
    directories get o+rx, files get o+r - and only ADD those bits, never narrowing
    the owner's. The staged files are the candidate's own code, not secret, in a
    short-lived temp dir removed by run()'s finally block.

    This is host-side only and changes no container isolation flag: the mount stays
    read-only (:ro) and --user stays 1000:1000 in _run_argv, so the candidate gains
    nothing it could not already do (it was always meant to read /sandbox); this
    only fixes the host-side permission so that intended read works on Linux. macOS
    Docker Desktop ignores host uid/mode, so the widening is harmless there.
    """
    workdir = Path(tempfile.mkdtemp(prefix="darwin_sbx_"))
    for fname, content in files.items():
        path = workdir / fname
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    # Walk top-down (os.walk yields workdir itself first) granting non-owner
    # traverse/read on every directory and read on every file, regardless of the
    # host umask.
    for root, _dirs, fnames in os.walk(workdir):
        os.chmod(root, stat.S_IMODE(os.stat(root).st_mode) | 0o055)
        for fname in fnames:
            fpath = os.path.join(root, fname)
            os.chmod(fpath, stat.S_IMODE(os.stat(fpath).st_mode) | 0o044)
    return workdir


def _extra_security_opt_args(extra_security_opts):
    """Expand opt-in extra security options into --security-opt argv pairs. Empty
    (the default) expands to nothing, so the produced argv is byte-identical to the
    1.0 lockdown; each entry is appended as an ADDITIONAL --security-opt, never
    replacing a lockdown flag (opt-in only adds restriction). See decision 0033."""
    args = []
    for opt in extra_security_opts:
        args += ["--security-opt", opt]
    return args


def _run_argv(name, workdir, command, image, memory, cpus, pids,
              extra_security_opts=None):
    """The locked-down `docker run` argv. Every flag here is one lockdown item.

    extra_security_opts is the OPT-IN defense-in-depth hook (P6.4.1, decision 0033):
    None (the default) uses the module-level EXTRA_SECURITY_OPTS, which is empty
    unless the operator set DARWIN_SANDBOX_EXTRA_SECURITY_OPTS, so by default the
    produced argv is byte-identical to the 1.0 lockdown. Any entries are appended as
    ADDITIONAL --security-opt options on top of the lockdown; nothing here is removed
    or altered. Read at CALL time (not bound as a def-time default) so an operator
    env var and tests both take effect."""
    opts = EXTRA_SECURITY_OPTS if extra_security_opts is None else extra_security_opts
    return [
        "docker", "run",
        "--name", name,
        "--network", "none",              # no network
        "--memory", memory,
        "--memory-swap", memory,          # == memory -> swap disabled -> real OOM
        "--cpus", str(cpus),              # CPU cap
        "--pids-limit", str(pids),        # process cap -> contains fork bombs
        "--read-only",                    # read-only root filesystem
        "--tmpfs", "/tmp:rw,size=64m,mode=1777",  # only writable area, in RAM
        "--cap-drop", "ALL",              # drop all Linux capabilities
        "--security-opt", "no-new-privileges",
        # OPT-IN extras (off by default): zero elements when unset, so the argv above
        # and below is unchanged; appended here as additional --security-opt entries.
        *_extra_security_opt_args(opts),
        "--user", "1000:1000",            # non-root (image USER is also sandbox)
        "-v", f"{workdir}:/sandbox:ro",   # the ONLY host path, read-only
        "-w", "/sandbox",
        "-e", "HOME=/tmp",                # writable HOME on the read-only root
        "-e", "TMPDIR=/tmp",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "PYTHONPYCACHEPREFIX=/tmp",
        image,
        *command,
    ]


def _classify(exit_code, oom):
    """Map a finished container's exit code to the shared taxonomy. OOM is an
    abnormal kill -> CRASHED. Docker reports a signal death as 128+signal, so
    exit codes >= 128 are signal deaths -> CRASHED; 0 is OK; any other non-zero
    exit (assertion=1, exception=1, ModuleNotFound=1, and docker infra errors
    125/126/127) is FAILED, with docker's stderr captured so infra errors show."""
    if oom:
        return CRASHED
    if exit_code == 0:
        return OK
    if exit_code is not None and 0 < exit_code < 128:
        return FAILED
    # Version-robust: an OOM kill is SIGKILL -> exit 137 (>= 128), so it lands here
    # as CRASHED even when the cgroup-dependent .State.OOMKilled flag is unset.
    return CRASHED


def _inspect(name):
    """Return (exit_code, oom_killed) from `docker inspect`, or (None, False) if it
    cannot be read. Bounded; never hangs the caller."""
    rc, out, _ = _docker(
        ["inspect", "--format", "{{.State.ExitCode}} {{.State.OOMKilled}}", name])
    if rc != 0:
        return None, False
    parts = out.split()
    if len(parts) != 2 or not parts[0].lstrip("-").isdigit():
        return None, False
    return int(parts[0]), parts[1] == "true"


def _docker(args):
    """Run a `docker` subcommand with a hard timeout. Returns (rc, stdout, stderr);
    on timeout or launch failure returns a non-zero rc and empty output. Teardown
    and inspection rely on this never blocking longer than _OP_TIMEOUT."""
    try:
        p = subprocess.run(["docker", *args], capture_output=True, text=True,
                           timeout=_OP_TIMEOUT)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "docker timed out"
    except OSError as e:
        return 125, "", str(e)


def _read_capped(path, limit):
    """Read up to `limit` bytes from `path`, appending a marker if it was larger.
    Bounds host memory regardless of how much the candidate printed."""
    try:
        with open(path, "rb") as f:
            data = f.read(limit + 1)
    except OSError:
        return ""
    if len(data) > limit:
        return (data[:limit].decode("utf-8", "replace")
                + f"\n...[truncated at {limit} bytes]")
    return data.decode("utf-8", "replace")


def _image_present_by_listing(image):
    """Secondary presence check via `docker image ls`, a DIFFERENT resolution path
    than inspect-by-tag: it reads the local image list rather than resolving the
    tag, so it does not inherit the containerd tag-resolution quirk where
    inspect-by-tag false-negatives on a present image. True iff `image` (repo:tag)
    appears in the listing. Goes through _docker, so it is bounded by the same
    _OP_TIMEOUT as the inspect and rm calls and can never block longer than that."""
    rc, out, _ = _docker(["image", "ls", "--format", "{{.Repository}}:{{.Tag}}"])
    if rc != 0:
        return False
    return image in out.splitlines()


def _require_image(image):
    """Fail fast with a build hint if the sandbox image is missing, instead of
    letting `docker run` return an opaque 125 later.

    inspect-by-tag is the primary check and the happy path (no extra docker call
    when it succeeds). Under containerd image storage that check can false-negative,
    returning non-zero even though the image is present (the tag-resolution quirk
    that recurred throughout development). So a non-zero inspect does NOT abort the
    run: we fall back to a second, different resolution path (listing the local
    images and confirming the tag is present) before concluding the image is truly
    absent. Only when BOTH the inspect and the listing fail to find it do we raise,
    with the same precise build-command remediation as before."""
    rc, _, _ = _docker(["image", "inspect", image])
    if rc == 0:
        return                                  # present by tag: happy path, no extra call
    if _image_present_by_listing(image):        # runs only on inspect failure
        return                                  # inspect false-negatived; image is present
    raise RuntimeError(
        f"sandbox image {image!r} not found. Build it once with:\n"
        f"    docker build -f tools/Dockerfile.sandbox -t {image} tools/")
