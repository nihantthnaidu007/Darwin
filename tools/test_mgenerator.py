"""Tests for the multi-file generator (Phase V2). Every test runs with NO API key
and NO Docker: the model call is exercised through an injected fake client, and
all parse / validation / materialize / path-safety paths are driven directly.

Coverage maps to THE BAR's edge cases:
- a well-formed 2-file and 4-file emission parse and validate;
- a syntax error in one file names the offending file;
- a missing __init__.py is rejected with that specific reason;
- an entry class not exposed in __init__.py is rejected specifically;
- an absolute path and a `..` traversal path are rejected and write nothing;
- a non-.py path is rejected;
- prose-only output with no file blocks is rejected;
- generate() with a fake client materializes a valid candidate and reports real
  token usage / cost, and writes nothing for an invalid one.
"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import mgenerator

ROOT = Path(__file__).resolve().parent.parent
META = json.loads((ROOT / "mcases" / "rate_limiter" / "meta.json").read_text(encoding="utf-8"))
ORIGINAL_FILES = mgenerator.read_unit(ROOT / "mcases" / "rate_limiter" / "original")


# ------------------------------------------------------------- helpers

def emit(files):
    """Render a {path: source} map as the `### FILE:` + fenced-block protocol the
    model is instructed to produce (and parse_emission reads back)."""
    return "\n\n".join(
        f"### FILE: {path}\n```python\n{src}\n```" for path, src in files.items()
    )


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
    """Stands in for anthropic.Anthropic(): no key, no network. Records the
    request kwargs so a test can assert what the model was (and was not) sent."""

    def __init__(self, text, in_tokens=120, out_tokens=340):
        self.text = text
        self.in_tokens = in_tokens
        self.out_tokens = out_tokens
        self.calls = []
        self.messages = _Messages(self)


GOOD_2FILE = {
    "__init__.py": "from .limiter import Limiter\n\n__all__ = [\"Limiter\"]",
    "limiter.py": (
        "class Limiter:\n"
        "    def __init__(self, rate, burst):\n"
        "        self.rate = rate\n"
        "        self.burst = burst\n"
    ),
}

GOOD_4FILE = {
    "__init__.py": "from .limiter import Limiter\n",
    "limiter.py": (
        "from .buckets import Registry\n"
        "from .checks import check\n\n"
        "class Limiter:\n"
        "    def __init__(self, rate, burst):\n"
        "        check(rate)\n"
        "        self.reg = Registry()\n"
    ),
    "buckets.py": "class Registry:\n    def __init__(self):\n        self.data = {}\n",
    "checks.py": "def check(x):\n    if x < 1:\n        raise ValueError('bad')\n",
}


# ----------------------------------------------------- well-formed emissions

def test_two_file_emission_parses_and_validates():
    files = mgenerator.parse_emission(emit(GOOD_2FILE))
    assert set(files) == {"__init__.py", "limiter.py"}
    assert "class Limiter" in files["limiter.py"]
    assert mgenerator.validate(files, "Limiter") is None


def test_four_file_emission_parses_and_validates():
    files = mgenerator.parse_emission(emit(GOOD_4FILE))
    assert set(files) == {"__init__.py", "limiter.py", "buckets.py", "checks.py"}
    assert mgenerator.validate(files, "Limiter") is None


# ----------------------------------------------------------- syntax error

def test_syntax_error_names_offending_file():
    bad = dict(GOOD_2FILE)
    bad["limiter.py"] = "class Limiter\n    pass\n"  # missing colon
    files = mgenerator.parse_emission(emit(bad))
    err = mgenerator.validate(files, "Limiter")
    assert err is not None
    assert "limiter.py" in err
    assert "not valid Python" in err


# --------------------------------------------------------- missing __init__

def test_missing_init_is_specific():
    files = mgenerator.parse_emission(emit({"limiter.py": GOOD_2FILE["limiter.py"]}))
    err = mgenerator.validate(files, "Limiter")
    assert err is not None
    assert "__init__.py" in err


# --------------------------------------------------- entry not exposed

def test_entry_not_exposed_is_specific():
    files = mgenerator.parse_emission(emit({
        "__init__.py": "# this package forgets to expose the entry class\n",
        "limiter.py": GOOD_2FILE["limiter.py"],
    }))
    err = mgenerator.validate(files, "Limiter")
    assert err is not None
    assert "Limiter" in err
    assert "expose" in err


def test_entry_defined_in_init_is_exposed():
    files = mgenerator.parse_emission(emit({"__init__.py": "class Limiter:\n    pass\n"}))
    assert mgenerator.validate(files, "Limiter") is None


def test_entry_reexported_is_exposed():
    files = mgenerator.parse_emission(emit(GOOD_2FILE))
    assert mgenerator.validate(files, "Limiter") is None


def test_entry_imported_under_other_name_is_not_exposed():
    files = mgenerator.parse_emission(emit({
        "__init__.py": "from .limiter import Limiter as Other\n",
        "limiter.py": GOOD_2FILE["limiter.py"],
    }))
    err = mgenerator.validate(files, "Limiter")
    assert err is not None and "expose" in err


# ----------------------------------------------------------- path safety

def test_absolute_path_rejected():
    files = mgenerator.parse_emission(emit({
        "__init__.py": GOOD_2FILE["__init__.py"],
        "/etc/evil.py": "x = 1\n",
    }))
    err = mgenerator.validate(files, "Limiter")
    assert err is not None and "absolute" in err


def test_dotdot_path_rejected():
    files = mgenerator.parse_emission(emit({
        "__init__.py": "from .a import Limiter\n",
        "../escape.py": "class Limiter:\n    pass\n",
    }))
    err = mgenerator.validate(files, "Limiter")
    assert err is not None and ".." in err


def test_non_py_path_rejected():
    files = mgenerator.parse_emission(emit({
        "__init__.py": GOOD_2FILE["__init__.py"],
        "notes.txt": "not python\n",
    }))
    err = mgenerator.validate(files, "Limiter")
    assert err is not None and "does not end in .py" in err


def test_windows_drive_path_rejected():
    err = mgenerator._path_error("C:\\Windows\\evil.py")
    assert err is not None and "absolute" in err


# ----------------------------------------------------------- prose only

def test_prose_only_is_invalid():
    text = "Sure! Here is a cleaner design. I will describe the approach in prose only."
    files = mgenerator.parse_emission(text)
    assert files == {}
    err = mgenerator.validate(files, "Limiter")
    assert err is not None and "no `### FILE:`" in err


# ----------------------------------------------------------- materialize

def test_materialize_creates_package(tmp_path):
    files = mgenerator.parse_emission(emit({
        "__init__.py": GOOD_2FILE["__init__.py"],
        "limiter.py": GOOD_2FILE["limiter.py"],
        "sub/extra.py": "VALUE = 1\n",
    }))
    assert mgenerator.validate(files, "Limiter") is None
    dest = mgenerator.materialize(files, tmp_path / "cand")
    dest = Path(dest)
    assert (dest / "__init__.py").exists()
    assert (dest / "sub" / "extra.py").exists()
    written = sorted(str(p.relative_to(dest)) for p in dest.rglob("*.py"))
    assert written == ["__init__.py", "limiter.py", "sub/extra.py"]
    for p in dest.rglob("*.py"):
        ast.parse(p.read_text(encoding="utf-8"))  # every file parses


def test_materialize_refuses_unsafe_path_and_writes_nothing(tmp_path):
    dest = tmp_path / "cand"
    with pytest.raises(ValueError):
        mgenerator.materialize({"../escape.py": "x = 1\n"}, dest)
    assert not dest.exists()  # nothing written, anywhere


# --------------------------------------------------- generate (fake client)

def test_generate_valid_materializes_and_reports_usage(tmp_path):
    client = FakeClient(emit(GOOD_4FILE))
    out = tmp_path / "cand"
    r = mgenerator.generate(META, ORIGINAL_FILES, client=client, out_dir=out)

    assert r.valid and r.error is None
    assert r.candidate_dir == str(out)
    assert (out / "__init__.py").exists()
    for p in out.rglob("*.py"):
        ast.parse(p.read_text(encoding="utf-8"))

    # Real token usage and cost from the API's own counts, via the reused PRICING.
    assert r.input_tokens == 120 and r.output_tokens == 340
    assert r.cost_usd == round(120 * (5.00 / 1e6) + 340 * (25.00 / 1e6), 6)

    # Honest by construction: the model never saw the suite, reference, or breaks.
    sent = client.calls[0]
    blob = sent["system"] + json.dumps(sent["messages"])
    for secret in ("test_suite", "golden", "breaks", "reference"):
        assert secret not in blob


def test_generate_first_gen_omits_previous_attempt():
    client = FakeClient(emit(GOOD_2FILE))
    mgenerator.generate(META, ORIGINAL_FILES, client=client)
    user = client.calls[0]["messages"][0]["content"]
    assert "previous attempt" not in user


def test_generate_later_gen_embeds_feedback_verbatim():
    client = FakeClient(emit(GOOD_2FILE))
    feedback = "REJECTED at the equivalence gate. sentinel-feedback-marker-42"
    mgenerator.generate(META, ORIGINAL_FILES, prev_files=GOOD_2FILE,
                        prev_feedback=feedback, client=client)
    user = client.calls[0]["messages"][0]["content"]
    assert "previous attempt" in user
    assert "sentinel-feedback-marker-42" in user  # embedded verbatim


def test_generate_invalid_writes_nothing(tmp_path):
    parent = tmp_path / "out"
    out = parent / "cand"
    client = FakeClient(emit({
        "__init__.py": "from .escape import Limiter\n",
        "../escape.py": "class Limiter:\n    pass\n",
    }))
    r = mgenerator.generate(META, ORIGINAL_FILES, client=client, out_dir=out)
    assert not r.valid
    assert ".." in r.error
    assert r.candidate_dir is None
    assert not out.exists()
    assert not parent.exists()  # generate created nothing on disk


def test_generate_thinking_params_gated_by_model():
    # A thinking-capable Opus model gets the adaptive-thinking + effort params.
    client = FakeClient(emit(GOOD_2FILE))
    mgenerator.generate(META, ORIGINAL_FILES, model="claude-opus-4-8", client=client)
    assert "thinking" in client.calls[0] and "output_config" in client.calls[0]

    # A model without the capability gets neither (stays model-configurable).
    client2 = FakeClient(emit(GOOD_2FILE))
    mgenerator.generate(META, ORIGINAL_FILES, model="claude-haiku-4-5", client=client2)
    assert "thinking" not in client2.calls[0] and "output_config" not in client2.calls[0]
