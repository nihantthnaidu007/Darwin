"""Determinism / reproducibility provenance (P5.2, decision 0022).

These run with NO API key and NO Docker. They prove three things:
  - the SDK version is read from the SDK (anthropic.__version__), never hardcoded;
  - request_provenance() is assembled from the SAME constants and helper generate()
    actually sends (request_kwargs), so the recorded config cannot drift from the
    request, and it is identical for two runs configured the same way;
  - both loops write that provenance block into run.json VERBATIM from the generator
    (single-file via loop.py, multi-file via mloop.py), re-typing nothing.

  cd tools && python -m pytest test_provenance.py -q -p no:cacheprovider
"""
import json
from types import SimpleNamespace

import anthropic

import generator
import llm_client
import loop
import mgenerator
import mloop

OPUS = "claude-opus-4-8"       # adaptive-thinking capable
HAIKU = "claude-haiku-4-5"     # no-thinking path


# ----------------------------------------------------------- sdk_version helper

def test_sdk_version_returns_anthropic_version():
    assert llm_client.sdk_version() == anthropic.__version__
    assert isinstance(llm_client.sdk_version(), str) and llm_client.sdk_version()


# ----------------------------------------------------------- provenance shape

def test_provenance_contains_temperature_model_and_sdk_version():
    prov = generator.request_provenance(OPUS)
    assert prov["temperature"] == 1.0
    assert prov["model"] == OPUS
    assert prov["sdk_version"] == anthropic.__version__
    assert prov["max_tokens"] == generator.MAX_TOKENS
    assert prov["thinking"] == {"adaptive": True, "effort": generator.EFFORT}


def test_provenance_no_thinking_path_records_temperature_and_no_adaptive():
    """On the no-thinking path the effective temperature is still an explicit 1.0,
    and the thinking decision is recorded as not-adaptive with no effort knob."""
    prov = generator.request_provenance(HAIKU)
    assert prov["temperature"] == 1.0
    assert prov["thinking"] == {"adaptive": False, "effort": None}


def test_provenance_assembled_from_request_config_not_retyped():
    """Every provenance value is derived from the SAME request configuration
    generate() sends (request_kwargs) and the module constants -- not independently
    typed literals -- so the record cannot drift from the request."""
    for model in (OPUS, HAIKU):
        prov = generator.request_provenance(model)
        kw = generator.request_kwargs(model)               # exactly what generate() splats
        assert prov["temperature"] == kw["temperature"]    # the temperature actually sent
        assert prov["max_tokens"] == generator.MAX_TOKENS
        assert prov["sdk_version"] == llm_client.sdk_version()
        assert prov["thinking"]["adaptive"] == ("thinking" in kw)
        assert prov["thinking"]["effort"] == (generator.EFFORT if "thinking" in kw else None)


def test_request_kwargs_sends_explicit_temperature_on_both_paths():
    assert generator.request_kwargs(OPUS)["temperature"] == 1.0
    assert "thinking" in generator.request_kwargs(OPUS)
    assert generator.request_kwargs(HAIKU)["temperature"] == 1.0
    assert "thinking" not in generator.request_kwargs(HAIKU)


def test_provenance_identical_for_same_model():
    """Two runs configured the same way record byte-identical provenance."""
    assert generator.request_provenance(OPUS) == generator.request_provenance(OPUS)
    assert mgenerator.request_kwargs(OPUS) == generator.request_kwargs(OPUS)  # multi-file reuses it


# ------------------------------------------------ run.json records provenance

def _genresult(model, code="def solve(nums):\n    return 0\n"):
    return generator.GenResult(code=code, raw_text="", valid=True, error=None,
                               model=model, input_tokens=10, output_tokens=20,
                               cost_usd=0.001)


def _ev(verdict="scored", wc=1.0):
    return SimpleNamespace(verdict=verdict, weighted_cost=wc, reason_code=None,
                           gate=None, flags=[], metrics={}, feedback="ok")


def test_loop_run_json_records_provenance_from_generator(tmp_path, monkeypatch):
    """The single-file loop writes the generator's provenance into run.json verbatim
    (no real API call): baseline + one improving generation, scripted."""
    evals = [_ev(wc=1.0), _ev(wc=0.5)]   # baseline, then an improving gen 1
    monkeypatch.setattr(loop, "RUNS", tmp_path)
    monkeypatch.setattr(loop, "evaluate", lambda *a, **k: evals.pop(0))
    monkeypatch.setattr(generator, "generate",
                        lambda meta, original, prev_code=None, prev_feedback=None,
                        model=None, client=None: _genresult(model))

    summary, run_dir = loop.run_loop("sum_evens", cap=1, plateau_limit=1, model=OPUS)

    written = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert written["provenance"] == generator.request_provenance(OPUS)
    assert summary["provenance"] == generator.request_provenance(OPUS)
    # The run record contains temperature, the model identifier, and the SDK version.
    assert written["provenance"]["temperature"] == 1.0
    assert written["provenance"]["model"] == OPUS
    assert written["provenance"]["sdk_version"] == anthropic.__version__


def test_mloop_run_json_records_provenance_from_generator(tmp_path):
    """The multi-file loop writes the same generator-sourced provenance into run.json,
    driven through its injectable generate/evaluate seams (no API, no Docker)."""
    files = {"__init__.py": "from .core import Limiter\n",
             "core.py": "class Limiter:\n    def __init__(self, rate, burst):\n"
                        "        self.rate = rate\n"}

    def fake_generate(meta, original_files, prev_files=None, prev_feedback=None,
                      model=None, client=None):
        return mgenerator.MGenResult(files=files, raw_text="", valid=True, error=None,
                                     candidate_dir=None, model=model, input_tokens=10,
                                     output_tokens=20, cost_usd=0.001)

    evals = [SimpleNamespace(verdict="scored", reason_code=None, gate=None,
                             metrics={"aggregate": {"file_count": 2}}, weighted_cost=wc,
                             metric_costs=None, flags=[], feedback="ok")
             for wc in (1.0, 0.5)]

    summary, run_dir = mloop.run_loop(
        "rate_limiter", cap=1, plateau_limit=1, model=OPUS,
        generate=fake_generate, evaluate=lambda *a, **k: evals.pop(0),
        run_root=tmp_path)

    written = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert written["provenance"] == generator.request_provenance(OPUS)
    assert summary["provenance"] == generator.request_provenance(OPUS)
    assert written["provenance"]["temperature"] == 1.0
    assert written["provenance"]["model"] == OPUS
    assert written["provenance"]["sdk_version"] == anthropic.__version__
