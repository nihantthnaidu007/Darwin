"""Unit tests for the Path-1 real-case construction tool darwin.build_real_case (P9.1).

Path 1 inverts build_case.py: the real open-source function is the ORIGINAL, the clean
reference.py is authored by hand, and the golden I/O is recorded from the original (the
ground truth). These tests pin the four gates the tool enforces mechanically:

  - the THRESHOLD gate (the original must be structurally non-trivial),
  - the SANITY gate (the original passes its own test suite),
  - the INTEGRITY gate (the authored reference preserves the original's behavior,
    verified by golden-I/O replay of the golden recorded FROM the original), and
  - the PROVENANCE requirement (a seed without provenance is refused).

NO Docker: the single container primitive verify_case calls (sandbox.run) is replaced by
a faithful in-process runner that executes the very same commands (pytest, then the
golden driver) via a subprocess of this interpreter. The real gates therefore run for
real -- a behavior-changing reference genuinely diverges on the golden replay and is
rejected -- without a Docker daemon, an LLM, or any API call.

  python -m pytest tests/test_build_real_case.py -q -p no:cacheprovider
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from darwin import build_real_case
from darwin import paths
from darwin import sandbox_container as sandbox

# --- fixtures: a real, naturally branch-heavy original and two authored references ----

# The "real" original: a letter-grade classifier with a redundant None guard. Its
# cyclomatic_total is comfortably >= 6 (an if + four elif + a guard if), so it clears
# the threshold. Negative scores fall through the chain and the guard maps them to "F".
ORIGINAL = '''\
def grade(score):
    """Letter grade from a numeric score; the redundant guard is the original's mess."""
    letter = None
    if score >= 90:
        letter = "A"
    elif score >= 80:
        letter = "B"
    elif score >= 70:
        letter = "C"
    elif score >= 60:
        letter = "D"
    elif score >= 0:
        letter = "F"
    if letter is None:
        letter = "F"
    return letter
'''

# The behavior-preserving authored reference: idiomatic early returns, the redundant
# guard removed. Negatives still fall through to "F", exactly as the original does.
REFERENCE_GOOD = """\
def grade(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"
"""

# A behavior-CHANGING reference. It passes the test suite (which never tests a negative
# score) but returns "INVALID" for negatives where the original returns "F". The golden
# recorded from the original DOES include negatives, so the integrity gate catches it on
# the golden replay -- proving an authored floor cannot silently change behavior even
# when the suite misses the change.
REFERENCE_BAD = """\
def grade(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    if score >= 0:
        return "F"
    return "INVALID"
"""

# The test suite imports from `candidate` (verify_case writes whichever file it checks
# as candidate.py). It deliberately tests NO negative score, so the bad reference slips
# past pytest and is caught only by the golden replay.
TEST_SUITE = """\
from candidate import grade


def test_a():
    assert grade(95) == "A"


def test_b():
    assert grade(85) == "B"


def test_c():
    assert grade(75) == "C"


def test_d():
    assert grade(65) == "D"


def test_f():
    assert grade(50) == "F"


def test_boundaries():
    assert grade(90) == "A"
    assert grade(80) == "B"
    assert grade(60) == "D"
"""

# Golden argument sets recorded from the original. Negatives (-5, -100) and several
# extra points (59, 0, 100, 70) are present but NOT all tested, so the golden set is not
# a subset of the suite's inputs (the Phase-0 mitigation) and exposes the bad reference.
ARG_SETS = [
    [95],
    [85],
    [75],
    [65],
    [50],
    [90],
    [80],
    [60],
    [59],
    [0],
    [-5],
    [-100],
    [100],
    [70],
]

# A trivial original that clears NEITHER threshold (cyclomatic_total 1, logical_loc < 20).
ORIGINAL_TRIVIAL = """\
def add(a, b):
    return a + b
"""

TEST_SUITE_TRIVIAL = """\
from candidate import add


def test_add():
    assert add(1, 2) == 3
"""

PROVENANCE = {
    "source_repo": "https://github.com/example/widgets",
    "file": "widgets/grading.py",
    "license": "MIT",
    "commit_or_version": "v1.4.2 (commit abc1234)",
}


# --- a Docker-free, in-process stand-in for sandbox_container.run ---------------------


def _local_run(files, command, timeout=30.0):
    """Execute verify_case's container commands in-process via a subprocess of this
    interpreter (no Docker). It writes the same files, runs the same command, and maps
    the outcome onto a ContainerResult, so verify_case.classify's real pytest gate and
    real golden replay both execute -- the gates genuinely bite."""
    with tempfile.TemporaryDirectory() as d:
        for name, content in files.items():
            (Path(d) / name).write_text(content, encoding="utf-8")
        argv = [sys.executable if a == "python" else a for a in command]
        try:
            proc = subprocess.run(
                argv, cwd=d, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired as e:
            return sandbox.ContainerResult(
                sandbox.TIMED_OUT,
                None,
                e.stdout or "",
                e.stderr or "",
                timeout,
                True,
                False,
            )
    status = sandbox.OK if proc.returncode == 0 else sandbox.FAILED
    return sandbox.ContainerResult(
        status, proc.returncode, proc.stdout, proc.stderr, 0.0, False, False
    )


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    """Point the package data root at a temp dir so CASES_DIR resolves there, never the
    real cases/. Cleared after the test."""
    (tmp_path / "cases").mkdir()
    paths.set_data_root(tmp_path)
    yield tmp_path
    paths.set_data_root(None)


@pytest.fixture
def no_docker(monkeypatch):
    """Replace the one container primitive with the in-process runner, so the gates run
    for real without Docker."""
    from darwin import verify_case

    monkeypatch.setattr(verify_case.sandbox, "run", _local_run)


def _seed(tmp_path, *, original, reference, suite, spec_extra=None, drop=()):
    """Write a seed dir (original.py, reference.py, test_suite.py, spec.json) and return
    its path. spec_extra overrides/extends the spec; `drop` removes top-level keys."""
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "original.py").write_text(original, encoding="utf-8")
    (seed / "reference.py").write_text(reference, encoding="utf-8")
    (seed / "test_suite.py").write_text(suite, encoding="utf-8")
    spec = {
        "case_id": "grade_case",
        "category": "over_abstraction",
        "difficulty": "easy",
        "entry_point": "grade",
        "description": "Letter grade from a numeric score. Pure, deterministic.",
        "arg_sets": ARG_SETS,
        "provenance": dict(PROVENANCE),
    }
    if spec_extra:
        spec.update(spec_extra)
    for key in drop:
        spec.pop(key, None)
    (seed / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return seed


# --- happy path ----------------------------------------------------------------------


def test_happy_path_assembles_correct_case(tmp_path, data_root, no_docker):
    """A real original + a behavior-preserving authored reference assembles a case:
    golden recorded FROM the original, baseline metrics frozen from BOTH, and meta.json
    carrying the provenance block and the measured threshold values."""
    seed = _seed(
        tmp_path, original=ORIGINAL, reference=REFERENCE_GOOD, suite=TEST_SUITE
    )

    status, case_id, reason = build_real_case.build(str(seed))

    assert status == "finalized", reason
    assert case_id == "grade_case"

    case_dir = data_root / "cases" / "grade_case"
    # The six on-disk files of a case are all present.
    for name in (
        "original.py",
        "reference.py",
        "test_suite.py",
        "golden_io.json",
        "baseline_metrics.json",
        "meta.json",
    ):
        assert (case_dir / name).exists(), name

    # Golden was recorded FROM the original (the key inversion). Every recorded output
    # equals the original's own output, including the negatives the suite never tests.
    golden = json.loads((case_dir / "golden_io.json").read_text())
    assert golden["entry_point"] == "grade"
    by_arg = {c["args"][0]: c["output"] for c in golden["cases"]}
    assert by_arg[95] == "A"
    assert by_arg[-5] == "F"  # the original's negative behavior, captured as truth
    assert by_arg[-100] == "F"

    # Baseline metrics are frozen from BOTH original (the 1.0 anchor) and reference
    # (the 0.0 floor), in the shape the evaluator reads.
    baseline = json.loads((case_dir / "baseline_metrics.json").read_text())
    assert set(baseline) == {"original", "reference_floor"}
    assert baseline["original"]["cyclomatic_total"] >= 6
    # The authored reference is structurally simpler than the messy original.
    assert (
        baseline["reference_floor"]["cyclomatic_total"]
        < baseline["original"]["cyclomatic_total"]
    )

    # meta carries provenance and the measured threshold record.
    meta = json.loads((case_dir / "meta.json").read_text())
    assert meta["case_id"] == "grade_case"
    assert meta["category"] == "over_abstraction"
    assert meta["entry_point"] == "grade"
    assert meta["constraints"] == build_real_case.CONSTRAINTS
    assert meta["provenance"] == PROVENANCE
    assert meta["threshold"]["met"] is True
    assert meta["threshold"]["rule"] == build_real_case.THRESHOLD_RULE
    # The recorded threshold values match what freeze measures on the original.
    assert (
        meta["threshold"]["cyclomatic_total"]
        == baseline["original"]["cyclomatic_total"]
    )
    assert meta["threshold"]["logical_loc"] == baseline["original"]["logical_loc"]


# --- the threshold gate bites --------------------------------------------------------


def test_threshold_gate_rejects_subthreshold_original(tmp_path, data_root, no_docker):
    """A sub-threshold original (cyclomatic_total < 6 AND logical_loc < 20) is REJECTED,
    and no case directory is written."""
    seed = _seed(
        tmp_path,
        original=ORIGINAL_TRIVIAL,
        reference=ORIGINAL_TRIVIAL,
        suite=TEST_SUITE_TRIVIAL,
        spec_extra={"entry_point": "add", "case_id": "trivial_case"},
    )

    status, case_id, reason = build_real_case.build(str(seed))

    assert status == "rejected"
    assert case_id == "trivial_case"
    assert "below complexity threshold" in reason
    assert "cyclomatic_total=1" in reason
    assert not (data_root / "cases" / "trivial_case").exists()


# --- the integrity gate bites --------------------------------------------------------


def test_integrity_gate_rejects_behavior_changing_reference(
    tmp_path, data_root, no_docker
):
    """A reference that does NOT preserve the original's behavior is REJECTED on the
    golden replay (the suite alone misses it), and no case is assembled. This proves an
    authored floor cannot silently change behavior."""
    seed = _seed(tmp_path, original=ORIGINAL, reference=REFERENCE_BAD, suite=TEST_SUITE)

    status, case_id, reason = build_real_case.build(str(seed))

    assert status == "rejected"
    assert "integrity gate" in reason
    # It failed specifically on the golden replay (behavior), not the pytest gate.
    assert "INVALID" in reason or "golden mismatch" in reason
    assert not (data_root / "cases" / "grade_case").exists()


def test_integrity_gate_passes_behavior_preserving_reference(
    tmp_path, data_root, no_docker
):
    """The companion to the gate-bites test: the SAME original with a behavior-preserving
    reference finalizes. The gate accepts a faithful cleanup and rejects only a change."""
    seed = _seed(
        tmp_path, original=ORIGINAL, reference=REFERENCE_GOOD, suite=TEST_SUITE
    )

    status, _, reason = build_real_case.build(str(seed))

    assert status == "finalized", reason


# --- the provenance requirement ------------------------------------------------------


def test_provenance_required(tmp_path, data_root, no_docker):
    """A spec with NO provenance block is rejected before any case is finalized."""
    seed = _seed(
        tmp_path,
        original=ORIGINAL,
        reference=REFERENCE_GOOD,
        suite=TEST_SUITE,
        drop=("provenance",),
    )

    status, _, reason = build_real_case.build(str(seed))

    assert status == "rejected"
    assert "provenance" in reason
    assert not (data_root / "cases" / "grade_case").exists()


def test_provenance_incomplete_rejected(tmp_path, data_root, no_docker):
    """A provenance block missing a required key (here license) is rejected, naming the
    missing key."""
    seed = _seed(
        tmp_path,
        original=ORIGINAL,
        reference=REFERENCE_GOOD,
        suite=TEST_SUITE,
        spec_extra={
            "provenance": {
                "source_repo": "r",
                "file": "f",
                "license": "  ",  # present but empty
                "commit_or_version": "v1",
            }
        },
    )

    status, _, reason = build_real_case.build(str(seed))

    assert status == "rejected"
    assert "license" in reason


# --- the license allowlist gate -------------------------------------------------------


def _prov_spec(license_value):
    """A minimal spec carrying a complete provenance block with the given license, for
    exercising _validate_provenance in isolation (no seed dir, no assembly)."""
    return {
        "provenance": {
            "source_repo": "https://github.com/example/widgets",
            "file": "widgets/grading.py",
            "license": license_value,
            "commit_or_version": "v1.4.2",
        }
    }


def test_allowlist_constant_has_the_nine_spdx_ids():
    """The allowlist is a stated module constant a future case author can read: exactly
    the nine permissive SPDX ids the methodology admits."""
    assert build_real_case.PERMISSIVE_LICENSES == (
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "Apache-2.0",
        "ISC",
        "0BSD",
        "Unlicense",
        "Python-2.0",
        "PSF-2.0",
    )


@pytest.mark.parametrize(
    "license_value",
    [
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "Apache-2.0",
        "ISC",
        "0BSD",
        "Unlicense",
        "Python-2.0",
        "PSF-2.0",
        "mit",  # case-insensitive
        "apache-2.0",
        "  MIT  ",  # whitespace-trimmed
    ],
)
def test_license_gate_accepts_permissive_ids(license_value):
    """Every permissive SPDX id passes the license gate, case-insensitively and with
    surrounding whitespace trimmed."""
    ok, reason = build_real_case._validate_provenance(_prov_spec(license_value))
    assert ok, reason
    assert reason is None


@pytest.mark.parametrize(
    "license_value",
    [
        "GPL-3.0",
        "AGPL-3.0",
        "LGPL-3.0",
        "GPL-2.0",
        "MPL-2.0",
        "BSD License",
        "Proprietary",
    ],
)
def test_license_gate_rejects_non_permissive(license_value):
    """A copyleft license, or an unrecognized / free-form string that is not an exact
    permissive SPDX id, is rejected by the license gate. The reason names the recorded
    license and states the allowlist."""
    ok, reason = build_real_case._validate_provenance(_prov_spec(license_value))
    assert not ok
    assert repr(license_value) in reason  # names the recorded license verbatim
    assert "allowlist" in reason
    assert "MIT" in reason  # states the allowlist


def test_license_gate_rejects_gpl_before_any_assembly(tmp_path, data_root):
    """A GPL-3.0 seed is REJECTED before any assembly: no case directory is written, and
    the message names GPL-3.0. NOTE no `no_docker` fixture -- the license gate runs ahead
    of the sanity/integrity gates (which would need the container), so this rejects
    without ever touching Docker, proving the gate is the first, cheapest check."""
    seed = _seed(
        tmp_path,
        original=ORIGINAL,
        reference=REFERENCE_GOOD,
        suite=TEST_SUITE,
        spec_extra={"provenance": {**PROVENANCE, "license": "GPL-3.0"}},
    )

    status, case_id, reason = build_real_case.build(str(seed))

    assert status == "rejected"
    assert case_id == "grade_case"
    assert "'GPL-3.0'" in reason  # names the recorded license
    assert "allowlist" in reason and "MIT" in reason  # states the allowlist
    assert not (data_root / "cases" / "grade_case").exists()  # no case dir written


def test_license_gate_rejects_unrecognized_string_before_any_assembly(
    tmp_path, data_root
):
    """An unrecognized (free-form, non-SPDX) license string is rejected before assembly;
    the tool does not normalize it. No case directory is written."""
    seed = _seed(
        tmp_path,
        original=ORIGINAL,
        reference=REFERENCE_GOOD,
        suite=TEST_SUITE,
        spec_extra={"provenance": {**PROVENANCE, "license": "BSD License"}},
    )

    status, _, reason = build_real_case.build(str(seed))

    assert status == "rejected"
    assert "'BSD License'" in reason
    assert not (data_root / "cases" / "grade_case").exists()


def test_license_gate_accepts_mit_case_assembles(tmp_path, data_root, no_docker):
    """The positive integration: an MIT-licensed seed passes the license gate and the
    case assembles end to end (the default PROVENANCE records license MIT)."""
    seed = _seed(
        tmp_path, original=ORIGINAL, reference=REFERENCE_GOOD, suite=TEST_SUITE
    )

    status, _, reason = build_real_case.build(str(seed))

    assert status == "finalized", reason
    assert (data_root / "cases" / "grade_case" / "meta.json").exists()


# --- the sanity gate (the original must pass its own suite) ---------------------------


def test_sanity_gate_rejects_original_failing_its_suite(tmp_path, data_root, no_docker):
    """If the original does not pass its own test suite, the case is rejected: the suite
    must genuinely capture the real function's behavior."""
    broken_suite = TEST_SUITE + "\n\ndef test_wrong():\n    assert grade(95) == 'Z'\n"
    seed = _seed(
        tmp_path, original=ORIGINAL, reference=REFERENCE_GOOD, suite=broken_suite
    )

    status, _, reason = build_real_case.build(str(seed))

    assert status == "rejected"
    assert "does not pass its own test suite" in reason
    assert not (data_root / "cases" / "grade_case").exists()


# --- overwrite protection ------------------------------------------------------------


def test_refuses_to_overwrite_existing_case(tmp_path, data_root, no_docker):
    """An already-finalized case is not overwritten without --force."""
    seed = _seed(
        tmp_path, original=ORIGINAL, reference=REFERENCE_GOOD, suite=TEST_SUITE
    )
    assert build_real_case.build(str(seed))[0] == "finalized"

    status, _, reason = build_real_case.build(str(seed))
    assert status == "refused"
    assert "--force" in reason

    # --force regenerates it (the new seed passes every gate).
    status, _, _ = build_real_case.build(str(seed), force=True)
    assert status == "finalized"


# --- import-safety and the lazy CASES_DIR --------------------------------------------


def test_cases_dir_is_lazy(monkeypatch):
    """CASES_DIR resolves through paths.cases_dir at ACCESS time, never at import."""
    sentinel = Path("/sentinel/cases")
    monkeypatch.setattr(paths, "cases_dir", lambda: sentinel)
    assert build_real_case.CASES_DIR == sentinel


def test_unknown_module_attr_raises():
    """The PEP 562 __getattr__ only serves CASES_DIR; anything else is AttributeError."""
    with pytest.raises(AttributeError):
        build_real_case.NOPE  # noqa: B018


def test_module_imports_without_data_resolution():
    """Importing build_real_case must do NO data-root resolution at import (the v0.8
    invariant). Proven in a fresh interpreter by sabotaging the resolver BEFORE import:
    if the import resolved data, it would raise; instead import succeeds, and only the
    later CASES_DIR access hits the resolver. Location-independent: it does not depend on
    running outside a checkout (the clean-venv form is exercised by SUCCESS CRITERIA 1)."""
    code = (
        "from darwin import paths\n"
        "def boom(*a, **k):\n"
        "    raise RuntimeError('RESOLVER_CALLED')\n"
        "paths.data_root = boom\n"  # any resolution now blows up
        "import darwin.build_real_case as m\n"  # must NOT touch the resolver
        "assert callable(m.build)\n"
        "print('IMPORT_OK')\n"
        "try:\n"
        "    m.CASES_DIR\n"  # this SHOULD hit the (sabotaged) resolver
        "except RuntimeError as e:\n"
        "    print('DEFERRED' if 'RESOLVER_CALLED' in str(e) else 'WRONG')\n"
        "else:\n"
        "    print('NOT_DEFERRED')\n"
    )
    src = str(Path(build_real_case.__file__).resolve().parents[1])
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": src, "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stderr
    assert "IMPORT_OK" in proc.stdout, proc.stdout + proc.stderr
    assert "DEFERRED" in proc.stdout, proc.stdout + proc.stderr


# --- the CLI entry point -------------------------------------------------------------


def test_main_finalized(tmp_path, data_root, no_docker, monkeypatch, capsys):
    seed = _seed(
        tmp_path, original=ORIGINAL, reference=REFERENCE_GOOD, suite=TEST_SUITE
    )
    monkeypatch.setattr(sys, "argv", ["build_real_case.py", str(seed)])
    build_real_case.main()
    assert "FINALIZED grade_case" in capsys.readouterr().out


def test_main_rejected_exits_one(tmp_path, data_root, no_docker, monkeypatch, capsys):
    seed = _seed(
        tmp_path,
        original=ORIGINAL_TRIVIAL,
        reference=ORIGINAL_TRIVIAL,
        suite=TEST_SUITE_TRIVIAL,
        spec_extra={"entry_point": "add", "case_id": "trivial_case"},
    )
    monkeypatch.setattr(sys, "argv", ["build_real_case.py", str(seed)])
    with pytest.raises(SystemExit) as ei:
        build_real_case.main()
    assert ei.value.code == 1
    assert "NOT FINALIZED trivial_case" in capsys.readouterr().out


def test_main_refused_exits_two(tmp_path, data_root, no_docker, monkeypatch, capsys):
    seed = _seed(
        tmp_path, original=ORIGINAL, reference=REFERENCE_GOOD, suite=TEST_SUITE
    )
    assert build_real_case.build(str(seed))[0] == "finalized"
    monkeypatch.setattr(sys, "argv", ["build_real_case.py", str(seed)])
    with pytest.raises(SystemExit) as ei:
        build_real_case.main()
    assert ei.value.code == 2
    assert "REFUSED grade_case" in capsys.readouterr().out


def test_main_usage_error_on_wrong_argc(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build_real_case.py"])
    with pytest.raises(SystemExit):
        build_real_case.main()
