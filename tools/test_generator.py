"""Tests for the single-function generator (tools/generator.py). Like the
multi-file suite, every test runs with NO API key and NO network: the model call
is exercised through an injected fake client, and the hardening behaviors are
checked directly.

Coverage maps to THE BAR's M0 leftovers:
- the happy path is unchanged — a valid code block yields the same GenResult shape
  and the default model still sends adaptive-thinking + effort params;
- an unknown model name runs and does NOT enable thinking;
- a model without the capability (Haiku) omits the thinking params;
- invalid model output is not fatal (returned as an invalid GenResult);
- an injected client neither loads .env nor needs a key;
- importing the module does not mutate the environment (no import-time side effect).
"""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import generator

TOOLS = Path(__file__).resolve().parent

META = {"entry_point": "solve", "description": "Sum the even numbers.",
        "constraints": "Keep the signature."}
ORIGINAL = "def solve(nums):\n    return sum(n for n in nums if n % 2 == 0)\n"
GOOD = "```python\ndef solve(nums):\n    return sum(n for n in nums if not n % 2)\n```"


# ------------------------------------------------------------- fake client

class _Messages:
    def __init__(self, outer):
        self.outer = outer

    def create(self, **kwargs):
        self.outer.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.outer.text)],
            usage=SimpleNamespace(input_tokens=self.outer.in_tokens,
                                  output_tokens=self.outer.out_tokens),
        )


class FakeClient:
    """Stands in for anthropic.Anthropic(): no key, no network. Records request
    kwargs so a test can assert what the model was (and was not) sent."""

    def __init__(self, text, in_tokens=100, out_tokens=200):
        self.text = text
        self.in_tokens = in_tokens
        self.out_tokens = out_tokens
        self.calls = []
        self.messages = _Messages(self)


# ------------------------------------------------------------- happy path

def test_happy_path_returns_genresult():
    client = FakeClient(GOOD)
    r = generator.generate(META, ORIGINAL, client=client)
    assert r.valid and r.error is None
    assert "def solve" in r.code
    assert r.model == generator.DEFAULT_MODEL
    assert r.input_tokens == 100 and r.output_tokens == 200
    assert r.cost_usd == round(100 * (5.00 / 1e6) + 200 * (25.00 / 1e6), 6)


def test_default_model_sends_thinking_and_effort():
    client = FakeClient(GOOD)
    generator.generate(META, ORIGINAL, client=client)  # default model = claude-opus-4-8
    sent = client.calls[0]
    assert sent["thinking"] == {"type": "adaptive"}
    assert sent["output_config"] == {"effort": generator.EFFORT}


# ------------------------------------------------- model capability gating

def test_unknown_model_runs_without_thinking():
    client = FakeClient(GOOD)
    r = generator.generate(META, ORIGINAL, model="claude-zephyr-9", client=client)
    assert r.valid                                # it runs, no crash
    sent = client.calls[0]
    assert "thinking" not in sent and "output_config" not in sent


def test_haiku_omits_thinking_params():
    client = FakeClient(GOOD)
    generator.generate(META, ORIGINAL, model="claude-haiku-4-5", client=client)
    sent = client.calls[0]
    assert "thinking" not in sent and "output_config" not in sent


# ---------------------------------------------------- invalid not fatal

def test_prose_only_is_invalid_not_raised():
    client = FakeClient("Sure, here is how I would simplify it, described in words only.")
    r = generator.generate(META, ORIGINAL, client=client)
    assert not r.valid                   # invalid, but never raised
    assert r.error is not None


def test_wrong_entry_point_is_invalid_not_raised():
    client = FakeClient("```python\ndef other(nums):\n    return 0\n```")
    r = generator.generate(META, ORIGINAL, client=client)
    assert not r.valid
    assert "solve" in r.error            # names the missing entry point


def test_syntax_error_is_invalid_not_raised():
    client = FakeClient("```python\ndef solve(nums)\n    return 0\n```")  # missing colon
    r = generator.generate(META, ORIGINAL, client=client)
    assert not r.valid
    assert "not valid Python" in r.error


# ------------------------------------------------- no env mutation

def test_injected_client_does_not_load_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = FakeClient(GOOD)
    generator.generate(META, ORIGINAL, client=client)
    # An injected client needs no key and triggers no .env load.
    import os
    assert os.environ.get("ANTHROPIC_API_KEY") is None


def test_import_is_side_effect_free():
    script = (
        "import os, sys; sys.path.insert(0, '.'); "
        "before = dict(os.environ); import generator; "
        "assert dict(os.environ) == before, 'import mutated env'; print('side-effect-free')"
    )
    r = subprocess.run([sys.executable, "-c", script], cwd=str(TOOLS),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "side-effect-free" in r.stdout
