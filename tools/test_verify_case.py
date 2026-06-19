"""Direct unit tests for the correctness-and-behavior gate verify_case.classify (H1,
P7.2).

classify is the gatekeeper: Layer 1 (pytest) then Layer 2 (golden replay), the first
failing gate decides, and the golden replay sends the candidate the INPUTS only -- the
oracle (the expected outputs) never crosses the container boundary (decision 0003).
classify was exercised only indirectly (through evaluator and the end-to-end runs), so
a regression in the gate ordering, the failing-gate taxonomy, or the withheld-oracle
invariant could pass the suite. These tests pin each, with NO Docker: the single
container primitive verify_case calls (sandbox.run) is replaced by a deterministic
fake that records exactly what crossed the boundary and plays the trusted driver back
when a real replay is expected, so classify's own parsing and comparison run for real.

  cd tools && python -m pytest test_verify_case.py -q -p no:cacheprovider
"""

import json
import re
import sys

import pytest

import sandbox_container as sandbox
import verify_case

# Golden outputs carry distinctive sentinels so a test can prove the oracle never
# crosses the boundary: these strings must NOT appear in any file sent to the
# container for the golden gate.
ORACLE_A = "ORACLE_OUTPUT_A_8c1f"
ORACLE_B = "ORACLE_OUTPUT_B_4d2e"
GOLDEN = {
    "entry_point": "f",
    "cases": [
        {"args": [1, 2], "kwargs": {}, "output": ORACLE_A},
        {"args": [3], "kwargs": {"k": 4}, "output": ORACLE_B},
    ],
}

# secrets.token_hex(16) -> 32 hex chars; it is the only 32-hex single-quoted literal
# in the generated driver source, so this picks out the per-run framing token.
_TOKEN_RE = re.compile(r"'([0-9a-f]{32})'")


def _result(status, exit_code=0, stdout="", stderr=""):
    """A ContainerResult mirroring what sandbox_container.run would return."""
    return sandbox.ContainerResult(
        status, exit_code, stdout, stderr, 0.01, status == sandbox.TIMED_OUT, False
    )


def _token(driver_src):
    m = _TOKEN_RE.search(driver_src)
    assert m is not None, "per-run token not found in the generated driver source"
    return m.group(1)


def _golden_emit(results):
    """A golden-gate response that plays the trusted in-container driver: it reads the
    per-run token out of the driver source classify generated and frames `results`
    exactly as the real driver would, so classify's own _extract_results parses it."""

    def respond(files):
        token = _token(files["driver.py"])
        framed = "\n" + token + json.dumps({"results": results}) + "\n"
        return _result(sandbox.OK, 0, stdout=framed)

    return respond


class _FakeSandbox:
    """Stand-in for sandbox_container.run, dispatching by command: the pytest gate
    (Layer 1) and the golden driver (Layer 2) get separately configured responses.
    Every call's files / command are recorded, so a test can assert what crossed the
    container boundary and whether the golden gate ran at all. A response of None for a
    gate raises if that gate is reached -- the direct way to prove a gate was skipped."""

    def __init__(self, pytest_resp, golden_resp=None):
        self._pytest = pytest_resp
        self._golden = golden_resp
        self.calls = []

    def run(self, files, command, timeout=10.0):
        self.calls.append(
            {"files": dict(files), "command": list(command), "timeout": timeout}
        )
        resp = self._pytest if "pytest" in command else self._golden
        if resp is None:
            raise AssertionError("Layer 2 (golden replay) ran when it should not have")
        return resp(files) if callable(resp) else resp


@pytest.fixture
def paths(tmp_path):
    """The three on-disk inputs classify reads: a candidate, a test suite, and a golden
    I/O file. Their CONTENT is immaterial here (the fake decides every outcome); only
    the golden JSON must be well-formed because classify parses it host-side."""
    cand = tmp_path / "candidate.py"
    cand.write_text("def f(*a, **k):\n    return None\n", encoding="utf-8")
    suite = tmp_path / "test_suite.py"
    suite.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    golden = tmp_path / "golden_io.json"
    golden.write_text(json.dumps(GOLDEN), encoding="utf-8")
    return str(cand), str(suite), str(golden)


def _install(monkeypatch, fake):
    monkeypatch.setattr(verify_case.sandbox, "run", fake.run)


# --- gate ordering: Layer 1 before Layer 2, first failing gate decides -------
def test_pytest_failure_decides_and_skips_golden(paths, monkeypatch):
    """When the pytest gate fails, classify returns gate == 'tests' and the golden
    replay is NEVER executed (the golden response raises if reached)."""
    fake = _FakeSandbox(
        pytest_resp=_result(sandbox.FAILED, 1, stdout="E   assert 1 == 2\n"),
        golden_resp=None,
    )
    _install(monkeypatch, fake)

    r = verify_case.classify(*paths)

    assert r.ok is False
    assert r.gate == "tests"
    assert r.code == verify_case.TESTS_FAILED
    assert len(fake.calls) == 1  # only the pytest gate ran
    assert "pytest" in fake.calls[0]["command"]


def test_golden_mismatch_when_pytest_passes(paths, monkeypatch):
    """When pytest passes but the golden replay diverges, the deciding gate is 'golden'
    with a behavior-mismatch code -- Layer 2 is reached only after Layer 1 passes."""
    fake = _FakeSandbox(
        pytest_resp=_result(sandbox.OK, 0),
        golden_resp=_golden_emit(["WRONG", ORACLE_B]),
    )  # first case diverges
    _install(monkeypatch, fake)

    r = verify_case.classify(*paths)

    assert r.ok is False
    assert r.gate == "golden"
    assert r.code == verify_case.BEHAVIOR_MISMATCH
    assert len(fake.calls) == 2  # both gates ran, in order
    assert "pytest" in fake.calls[0]["command"]
    assert fake.calls[1]["command"] == ["python", "driver.py"]


def test_both_gates_pass_ok_true_gate_none(paths, monkeypatch):
    """When both gates pass, classify returns ok True and gate None."""
    fake = _FakeSandbox(
        pytest_resp=_result(sandbox.OK, 0),
        golden_resp=_golden_emit([ORACLE_A, ORACLE_B]),
    )  # matches golden exactly
    _install(monkeypatch, fake)

    r = verify_case.classify(*paths)

    assert r.ok is True
    assert r.gate is None
    assert r.code is None


# --- the core invariant: the candidate never sees the oracle ----------------
def test_golden_payload_withholds_the_oracle(paths, monkeypatch):
    """Decision 0003. The golden gate sends the candidate the INPUTS only. The payload
    handed to the container carries args and kwargs for every case but never the
    expected output, and NO file crossing the boundary contains any golden output."""
    fake = _FakeSandbox(
        pytest_resp=_result(sandbox.OK, 0),
        golden_resp=_golden_emit([ORACLE_A, ORACLE_B]),
    )
    _install(monkeypatch, fake)

    r = verify_case.classify(*paths)
    assert r.ok is True  # the replay actually completed

    golden_files = fake.calls[1]["files"]  # the Layer 2 (driver) call
    payload = json.loads(golden_files["inputs.json"])
    assert set(payload) == {"entry_point", "cases"}  # no expected-output key at all
    for sent, original in zip(payload["cases"], GOLDEN["cases"]):
        assert sent["args"] == original["args"]
        assert sent["kwargs"] == original["kwargs"]
        assert "output" not in sent  # the oracle is withheld
    # The strongest form: no golden output value appears in ANY file sent in -- not the
    # inputs, not the candidate, not the driver.
    for name, content in golden_files.items():
        assert ORACLE_A not in content, name
        assert ORACLE_B not in content, name


# --- the failing-gate taxonomy ----------------------------------------------
@pytest.mark.parametrize(
    "status, exit_code, expected_code",
    [
        (sandbox.TIMED_OUT, None, verify_case.TIMED_OUT),
        (sandbox.CRASHED, None, verify_case.CRASHED),
        (sandbox.FAILED, 1, verify_case.TESTS_FAILED),
        (sandbox.FAILED, 2, verify_case.COULD_NOT_RUN),
    ],
)
def test_taxonomy_layer1_pytest(paths, monkeypatch, status, exit_code, expected_code):
    """Failing-gate taxonomy at Layer 1: a timed-out, crashed, exit-1, and
    other-non-zero container result each map to the right reason code, all decided at
    the 'tests' gate."""
    fake = _FakeSandbox(pytest_resp=_result(status, exit_code), golden_resp=None)
    _install(monkeypatch, fake)

    r = verify_case.classify(*paths)

    assert r.ok is False
    assert r.gate == "tests"
    assert r.code == expected_code
    assert len(fake.calls) == 1  # decided at Layer 1


@pytest.mark.parametrize(
    "status, exit_code, expected_code",
    [
        (sandbox.TIMED_OUT, None, verify_case.TIMED_OUT),
        (sandbox.CRASHED, None, verify_case.CRASHED),
        (sandbox.FAILED, 1, verify_case.BEHAVIOR_MISMATCH),
        (sandbox.FAILED, 2, verify_case.COULD_NOT_RUN),
    ],
)
def test_taxonomy_layer2_golden(paths, monkeypatch, status, exit_code, expected_code):
    """At Layer 2 the same mapping applies, but an exit-1 (it ran and produced a wrong
    answer) is a behavior-mismatch, not tests-failed: the gate is 'golden' and the
    mismatch code is layer-specific."""
    fake = _FakeSandbox(
        pytest_resp=_result(sandbox.OK, 0), golden_resp=_result(status, exit_code)
    )
    _install(monkeypatch, fake)

    r = verify_case.classify(*paths)

    assert r.ok is False
    assert r.gate == "golden"
    assert r.code == expected_code
    assert len(fake.calls) == 2  # reached Layer 2


# --- fail closed: an unverifiable golden frame is not a pass ----------------
def test_golden_suppressed_output_fails_closed(paths, monkeypatch):
    """A golden replay that exits 0 but emits NO verifiable result frame fails closed:
    a replay we cannot verify is not a pass."""
    fake = _FakeSandbox(
        pytest_resp=_result(sandbox.OK, 0),
        golden_resp=_result(sandbox.OK, 0, stdout="nothing useful here\n"),
    )
    _install(monkeypatch, fake)

    r = verify_case.classify(*paths)

    assert r.ok is False
    assert r.gate == "golden"
    assert r.code == verify_case.COULD_NOT_RUN


def test_golden_double_frame_fails_closed(paths, monkeypatch):
    """Two token-framed result lines (a forged frame emitted alongside the real one)
    fail closed: a result is trusted only when EXACTLY ONE frame is present."""

    def two_frames(files):
        frame = _token(files["driver.py"]) + json.dumps(
            {"results": [ORACLE_A, ORACLE_B]}
        )
        return _result(sandbox.OK, 0, stdout="\n" + frame + "\n" + frame + "\n")

    fake = _FakeSandbox(pytest_resp=_result(sandbox.OK, 0), golden_resp=two_frames)
    _install(monkeypatch, fake)

    r = verify_case.classify(*paths)

    assert r.ok is False
    assert r.gate == "golden"
    assert r.code == verify_case.COULD_NOT_RUN


def test_golden_wrong_result_count_fails_closed(paths, monkeypatch):
    """A result frame whose length does not match the number of golden cases fails
    closed: a partial or corrupted replay is not a pass."""
    fake = _FakeSandbox(
        pytest_resp=_result(sandbox.OK, 0), golden_resp=_golden_emit([ORACLE_A])
    )  # 1 result for 2 golden cases
    _install(monkeypatch, fake)

    r = verify_case.classify(*paths)

    assert r.ok is False
    assert r.gate == "golden"
    assert r.code == verify_case.COULD_NOT_RUN


def test_golden_corrupt_single_frame_fails_closed(paths, monkeypatch):
    """A single token-framed line whose payload is not valid JSON fails closed via the
    parse-guard in _extract_results: a frame we cannot decode is not a pass."""

    def corrupt(files):
        framed = "\n" + _token(files["driver.py"]) + "not-json{" + "\n"
        return _result(sandbox.OK, 0, stdout=framed)

    fake = _FakeSandbox(pytest_resp=_result(sandbox.OK, 0), golden_resp=corrupt)
    _install(monkeypatch, fake)

    r = verify_case.classify(*paths)

    assert r.ok is False
    assert r.gate == "golden"
    assert r.code == verify_case.COULD_NOT_RUN


# --- the verify() boolean contract and the CLI entry point ------------------
def test_verify_boolean_contract(paths, monkeypatch):
    """verify() is the (ok, reason) wrapper build_case.py depends on: it returns the
    classify outcome as a bool plus a human-readable reason, on both pass and fail."""
    passing = _FakeSandbox(
        pytest_resp=_result(sandbox.OK, 0),
        golden_resp=_golden_emit([ORACLE_A, ORACLE_B]),
    )
    _install(monkeypatch, passing)
    ok, reason = verify_case.verify(*paths)
    assert ok is True
    assert isinstance(reason, str) and reason

    failing = _FakeSandbox(pytest_resp=_result(sandbox.FAILED, 1), golden_resp=None)
    _install(monkeypatch, failing)
    ok, reason = verify_case.verify(*paths)
    assert ok is False
    assert reason


def test_main_prints_pass_and_exits_zero(paths, monkeypatch, capsys):
    """The CLI prints PASS and exits 0 when the gate passes."""
    monkeypatch.setattr(verify_case, "verify", lambda *a: (True, "all matched"))
    monkeypatch.setattr(sys, "argv", ["verify_case.py", *paths])

    with pytest.raises(SystemExit) as ei:
        verify_case.main()

    assert ei.value.code == 0
    assert capsys.readouterr().out.strip() == "PASS"


def test_main_prints_fail_and_exits_one(paths, monkeypatch, capsys):
    """The CLI prints FAIL: <reason> and exits 1 when the gate fails."""
    monkeypatch.setattr(verify_case, "verify", lambda *a: (False, "boom reason"))
    monkeypatch.setattr(sys, "argv", ["verify_case.py", *paths])

    with pytest.raises(SystemExit) as ei:
        verify_case.main()

    assert ei.value.code == 1
    assert "FAIL: boom reason" in capsys.readouterr().out


def test_main_usage_error_on_wrong_argc(monkeypatch):
    """The CLI exits with a usage message when not given exactly three arguments."""
    monkeypatch.setattr(sys, "argv", ["verify_case.py"])

    with pytest.raises(SystemExit):
        verify_case.main()
