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
Run from tools/:
    python -m pytest test_sandbox_container.py -q -p no:cacheprovider
"""
import os
import shutil
import stat

import pytest

import sandbox_container

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
    assert (staged / "driver.py").read_text(encoding="utf-8").startswith("import pkg.mod")
    assert (staged / "pkg" / "mod.py").read_text(encoding="utf-8") == FILES["pkg/mod.py"]
