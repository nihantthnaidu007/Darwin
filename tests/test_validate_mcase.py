"""Regression test for the pytest-availability guard in validate_mcase.

validate_mcase runs each case's suite via `python -m pytest` in a subprocess
(see _run_suite). When the interpreter running validate_mcase lacks pytest, that
subprocess used to fail downstream with an error that looked like a case problem
rather than a missing dependency. _require_pytest now fails fast, naming pytest,
the active interpreter (sys.executable), and the remedy.

These tests need neither docker nor a real missing-pytest environment: the
spec-finder is injected, so absence and presence are simulated directly.

Run from tools/:
    python -m pytest test_validate_mcase.py -q -p no:cacheprovider
"""

import pytest

from darwin.validate_mcase import _require_pytest


def test_guard_fires_when_pytest_absent(capsys):
    """Finder reports pytest absent: the guard exits non-zero and the stderr
    message names pytest."""
    with pytest.raises(SystemExit) as exc:
        _require_pytest(find_spec=lambda name: None)
    assert exc.value.code != 0
    assert "pytest" in capsys.readouterr().err


def test_guard_silent_when_pytest_present():
    """The guard does not fire when pytest is importable: neither with an
    injected present finder nor with the real interpreter (which has pytest,
    being the one running this test). The normal validate path is unchanged."""
    assert _require_pytest(find_spec=lambda name: object()) is None
    assert _require_pytest() is None
