"""Tests for the bloat tool (src/darwin/bloat.py). Mirrors test_generator.py:
every test runs with NO API key and NO network — the model call is exercised
through an injected fake client, and the convergence onto the shared LLM-call
convention is checked directly.

Coverage:
- an injected client returns the stripped result, needs no key, and loads no .env;
- bloat's OWN request shape is sent through create_message unchanged (model,
  max_tokens=16000, adaptive thinking, its SYSTEM/USER prompts) and it does NOT
  adopt generator's temperature / output_config knobs;
- importing the module does not mutate the environment (no import-time side effect).
"""

import subprocess
import sys
from types import SimpleNamespace

from darwin import bloat, paths


# The directory that holds the darwin package (src/ in a checkout), put on the
# subprocess import path so `import darwin.bloat` resolves there.
SRC = paths.data_root() / "src"

REFERENCE = "def solve(nums):\n    return sum(n for n in nums if n % 2 == 0)\n"


# ------------------------------------------------------------- fake client


class _Messages:
    def __init__(self, outer):
        self.outer = outer

    def create(self, **kwargs):
        self.outer.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.outer.text)]
        )


class FakeClient:
    """Stands in for anthropic.Anthropic(): no key, no network. Records request
    kwargs so a test can assert what the model was (and was not) sent."""

    def __init__(self, text):
        self.text = text
        self.calls = []
        self.messages = _Messages(self)


# ------------------------------------------------- injected client / no key


def test_injected_client_returns_stripped_result(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ref = tmp_path / "reference.py"
    ref.write_text(REFERENCE, encoding="utf-8")
    client = FakeClient("```python\ndef solve(nums):\n    return 0\n```")
    out = bloat.bloat(str(ref), client=client)
    # Markdown fences stripped, exactly one trailing newline.
    assert out == "def solve(nums):\n    return 0\n"
    # An injected client needs no key and triggers no .env load.
    import os

    assert os.environ.get("ANTHROPIC_API_KEY") is None


def test_injected_client_does_not_load_env(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Make _load_dotenv loud: if it were ever called, the test would fail.
    def _boom():
        raise AssertionError("bloat() loaded .env despite an injected client")

    monkeypatch.setattr(bloat, "_load_dotenv", _boom)
    ref = tmp_path / "reference.py"
    ref.write_text(REFERENCE, encoding="utf-8")
    client = FakeClient("def solve(nums):\n    return 0\n")
    out = bloat.bloat(str(ref), client=client)
    assert out == "def solve(nums):\n    return 0\n"


# ------------------------------------------- bloat keeps its own request shape


def test_sends_bloats_own_request_params(tmp_path):
    ref = tmp_path / "reference.py"
    ref.write_text(REFERENCE, encoding="utf-8")
    client = FakeClient("def solve(nums):\n    return 0\n")
    bloat.bloat(str(ref), client=client)
    sent = client.calls[0]
    assert sent["model"] == bloat.MODEL == "claude-opus-4-8"
    assert sent["max_tokens"] == 16000
    assert sent["thinking"] == {"type": "adaptive"}
    assert sent["system"] == bloat.SYSTEM
    assert sent["messages"] == [
        {"role": "user", "content": bloat.USER.format(code=REFERENCE)}
    ]


def test_does_not_adopt_generator_sampling_params(tmp_path):
    """bloat preserves its own request shape: it must NOT add generator's pinned
    temperature or the effort/output_config knob (out-of-scope rule 2)."""
    ref = tmp_path / "reference.py"
    ref.write_text(REFERENCE, encoding="utf-8")
    client = FakeClient("def solve(nums):\n    return 0\n")
    bloat.bloat(str(ref), client=client)
    sent = client.calls[0]
    assert "temperature" not in sent
    assert "output_config" not in sent


# ------------------------------------------------------- no env mutation


def test_import_is_side_effect_free():
    script = (
        "import os, sys; sys.path.insert(0, '.'); "
        "before = dict(os.environ); import darwin.bloat; "
        "assert dict(os.environ) == before, 'import mutated env'; print('side-effect-free')"
    )
    r = subprocess.run(
        [sys.executable, "-c", script], cwd=str(SRC), capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    assert "side-effect-free" in r.stdout
