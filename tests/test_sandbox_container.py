"""Regression test for the sandbox staging permissions (V4 hardening).

DEFECT: sandbox_container.run() staged each run into tempfile.mkdtemp(), which
creates the directory mode 0o700 owned by the host user, then bind-mounted it
read-only at /sandbox while the container ran as --user 1000:1000. On a Linux
Docker host a bind mount preserves the host directory's owner and mode, so the
container's uid 1000 (a different uid than the host user) cannot traverse or read
a 0o700 directory owned by someone else: every candidate run failed with
"Permission denied: /sandbox/driver.py". macOS Docker Desktop masks this because
its file-sharing layer does not enforce host uid/mode, so the suite passed
locally while every CI run on ubuntu-latest failed. This was the open "isolation
verified on macOS only, native Linux unverified" ledger item.

FIX: the host-only helper sandbox_container._stage(files) -> Path does the
mkdtemp + write and then widens the staged tree so a non-owner uid can traverse
and read it: directories get o+rx, files get o+r. Container isolation is
unchanged (the mount stays :ro, --user stays 1000:1000, read-only root / tmpfs /
dropped caps / no-network all unchanged in _run_argv).

This test exercises _stage directly and NEVER invokes docker, so CI and any host
can run it. It FAILS on the pre-fix code (staging dir 0o700) and PASSES after.
Run from the repo root:
    python -m pytest tests/test_sandbox_container.py -q -p no:cacheprovider
"""

import os
import shutil
import stat

import pytest

from darwin import sandbox_container


# A files dict with a NESTED path, so the test covers both the mount root and a
# staged subdirectory: the container must traverse pkg/ to import pkg/mod.py.
FILES = {
    "driver.py": "import pkg.mod\nprint(pkg.mod.value())\n",
    "pkg/__init__.py": "",
    "pkg/mod.py": "def value():\n    return 42\n",
}


def _mode(path):
    """The permission bits of `path` (type bits stripped)."""
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.fixture
def staged():
    """Stage FILES through the real host-only helper and remove the temp dir after.
    run()'s finally block owns cleanup in production; here the test owns it."""
    workdir = sandbox_container._stage(FILES)
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def test_mount_root_traversable_and_readable_by_non_owner(staged):
    # o+rx on the mount root: the container's uid 1000 can enter /sandbox. This is
    # the bit the 0o700 default removed, the single cause of every CI failure.
    assert _mode(staged) & 0o005 == 0o005


def test_nested_subdir_traversable_by_non_owner(staged):
    # o+rx on the staged subdirectory: the container can traverse pkg/ to reach
    # pkg/mod.py. The fix must guarantee this regardless of the host umask.
    assert _mode(staged / "pkg") & 0o005 == 0o005


def test_staged_files_readable_by_non_owner(staged):
    # o+r on staged files at the root and inside the subdirectory: the container
    # can read the candidate code it is told to run.
    assert _mode(staged / "driver.py") & 0o004 == 0o004
    assert _mode(staged / "pkg" / "mod.py") & 0o004 == 0o004


def test_owner_access_preserved(staged):
    # The widening only ADDS non-owner bits; the owner keeps full access to the
    # tree (rwx on dirs, rw on files), so staging is not narrowed.
    assert _mode(staged) & 0o700 == 0o700
    assert _mode(staged / "pkg") & 0o700 == 0o700
    assert _mode(staged / "driver.py") & 0o600 == 0o600


def test_stage_writes_content_and_structure(staged):
    # The chmod walk must not damage staging: content and nested layout intact.
    assert (
        (staged / "driver.py").read_text(encoding="utf-8").startswith("import pkg.mod")
    )
    assert (staged / "pkg" / "mod.py").read_text(encoding="utf-8") == FILES[
        "pkg/mod.py"
    ]


# ---------------------------------------------------------------------------
# Image preflight robustness (P4.3): a false-negative `docker image inspect` by
# tag (the containerd tag-resolution quirk) must not abort the run. These tests
# stub sandbox_container._docker, so NO real docker is required.
# ---------------------------------------------------------------------------

IMG = sandbox_container.IMAGE


def _stub_docker(monkeypatch, handler):
    """Replace sandbox_container._docker with `handler` and record every call.
    Returns the calls list (each entry is the args list passed to _docker)."""
    calls = []

    def fake(args):
        calls.append(list(args))
        return handler(list(args))

    monkeypatch.setattr(sandbox_container, "_docker", fake)
    return calls


def test_require_image_present_by_tag_makes_no_extra_call(monkeypatch):
    # Happy path: inspect-by-tag succeeds, so the run proceeds with exactly one
    # docker call and never reaches the secondary listing.
    def handler(args):
        if args[:2] == ["image", "inspect"]:
            return (0, "[]", "")
        raise AssertionError(f"no extra docker call expected on success: {args}")

    calls = _stub_docker(monkeypatch, handler)
    sandbox_container._require_image(IMG)  # must not raise
    assert calls == [["image", "inspect", IMG]]  # exactly the one inspect call


def test_require_image_false_negative_proceeds_via_listing(monkeypatch):
    # The defect from finding B2: inspect-by-tag returns non-zero on a PRESENT
    # image. The secondary listing resolves it, so the run proceeds, not aborts.
    def handler(args):
        if args[:2] == ["image", "inspect"]:
            return (1, "", f"Error: No such image: {IMG}")  # false negative
        if args[:2] == ["image", "ls"]:
            return (0, f"python:3.13\n{IMG}\nbusybox:latest", "")
        return (1, "", "")

    calls = _stub_docker(monkeypatch, handler)
    sandbox_container._require_image(IMG)  # must NOT raise
    assert calls[0][:2] == ["image", "inspect"]  # primary tried first
    assert any(
        c[:2] == ["image", "ls"] for c in calls
    )  # secondary, different path, ran
    # The secondary call is NOT a second inspect-by-tag (it is a genuinely
    # different resolution mechanism).
    assert not any(c[:3] == ["image", "inspect", IMG] for c in calls[1:])


def test_require_image_genuinely_absent_raises_build_hint(monkeypatch):
    # Both checks fail to find it -> still fail fast with the precise build hint.
    def handler(args):
        if args[:2] == ["image", "inspect"]:
            return (1, "", "No such image")
        if args[:2] == ["image", "ls"]:
            return (0, "python:3.13\nbusybox:latest", "")  # tag absent from listing
        return (1, "", "")

    _stub_docker(monkeypatch, handler)
    with pytest.raises(RuntimeError) as ei:
        sandbox_container._require_image(IMG)
    msg = str(ei.value)
    assert "not found" in msg
    assert f"docker build -f docker/Dockerfile.sandbox -t {IMG} docker/" in msg
    assert IMG in msg


def test_require_image_secondary_check_is_timeout_bounded(monkeypatch):
    # The secondary listing goes through _docker (bounded by _OP_TIMEOUT). If it
    # times out, _docker returns the 124 sentinel, the fallback yields "absent",
    # and the run fails fast with the build hint rather than blocking.
    def handler(args):
        if args[:2] == ["image", "inspect"]:
            return (1, "", "")
        if args[:2] == ["image", "ls"]:
            return (124, "", "docker timed out")  # _docker timeout sentinel
        return (1, "", "")

    _stub_docker(monkeypatch, handler)
    with pytest.raises(RuntimeError):
        sandbox_container._require_image(IMG)


def test_image_present_by_listing_matches_exact_tag(monkeypatch):
    # The listing check confirms the exact repo:tag, not a loose substring.
    def handler(args):
        return (0, f"python:3.13\n{IMG}\nbusybox:latest", "")

    _stub_docker(monkeypatch, handler)
    assert sandbox_container._image_present_by_listing(IMG) is True

    def handler_absent(args):
        return (0, "python:3.13\nbusybox:latest", "")

    _stub_docker(monkeypatch, handler_absent)
    assert sandbox_container._image_present_by_listing(IMG) is False
