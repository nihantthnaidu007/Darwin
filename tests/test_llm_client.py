"""Tests for the shared LLM-call hardening (tools/llm_client.py). No API key and
no network: the retry + classification paths are driven through a real Anthropic
client wired to an httpx.MockTransport, so the SDK's own retry/backoff logic runs
exactly as it would in production while we script the HTTP responses. The backoff
sleep is neutralized so the tests stay fast and deterministic.

Coverage maps to THE BAR:
- a transient failure (429, then connection error) followed by success is handled
  without the call dying — the configured retries recover it;
- a retryable failure that exhausts the budget raises one clear, classified error
  (never a raw SDK stack trace);
- a fatal request error (400 / 401) raises a clear, classified error and is NOT
  retried;
- model capability is derived from the id: known models match today's behavior,
  a newer model keeps thinking, and an unknown/older id takes the no-thinking path.
"""

import anthropic
import httpx
import pytest

from darwin import llm_client


# ------------------------------------------------------------- harness


def _message_json():
    """A minimal but valid /v1/messages success body the SDK will parse."""
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-4-8",
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 11, "output_tokens": 7},
    }


def _error_json(kind, message):
    return {"type": "error", "error": {"type": kind, "message": message}}


def _client(handler, max_retries=llm_client.LLM_MAX_RETRIES):
    """A real Anthropic client whose HTTP layer is a MockTransport, with backoff
    sleeps neutralized. `handler(request) -> httpx.Response` scripts each attempt."""
    c = anthropic.Anthropic(
        api_key="sk-test",
        max_retries=max_retries,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    c._sleep_for_retry = lambda *a, **k: None  # no real backoff sleep in tests
    return c


def _create(client):
    return llm_client.create_message(
        client,
        model="claude-opus-4-8",
        max_tokens=64,
        messages=[{"role": "user", "content": "hi"}],
    )


# ------------------------------------------------- transient then success


def test_rate_limit_then_success_recovers():
    calls = {"n": 0}

    def handler(_request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429, json=_error_json("rate_limit_error", "slow down")
            )
        return httpx.Response(200, json=_message_json())

    resp = _create(_client(handler))
    assert calls["n"] == 2  # one retry, then success
    assert resp.content[0].text == "ok"  # the run did not die
    assert resp.usage.input_tokens == 11


def test_connection_error_then_success_recovers():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json=_message_json())

    resp = _create(_client(handler))
    assert calls["n"] == 2
    assert resp.content[0].text == "ok"


# ------------------------------------------------- retryable exhausted


def test_rate_limit_exhausted_raises_classified():
    calls = {"n": 0}

    def handler(_request):
        calls["n"] += 1
        return httpx.Response(429, json=_error_json("rate_limit_error", "nope"))

    with pytest.raises(llm_client.LLMCallError) as ei:
        _create(_client(handler, max_retries=2))

    assert calls["n"] == 3  # initial + 2 retries, all 429
    msg = str(ei.value)
    # The message reports the configured production budget (LLM_MAX_RETRIES); the
    # test overrode the client's max_retries only to keep the run fast.
    assert f"after {llm_client.LLM_MAX_RETRIES} automatic retries" in msg
    assert "transient and retryable" in msg
    assert "HTTP 429" in msg
    assert "Traceback" not in msg  # a clean message, not a stack trace
    # Describes the SDK's actual backoff, not a fabricated single ceiling figure.
    assert "exponential backoff" in msg
    assert "Retry-After" in msg
    assert "cumulative ceiling" not in msg  # the removed fabricated phrasing
    assert "15s" not in msg  # the removed fabricated figure
    # Still an anthropic.APIError so the loops' `except anthropic.APIError` still halts.
    assert isinstance(ei.value, anthropic.APIError)


def test_connection_error_exhausted_is_retryable():
    def handler(request):
        raise httpx.ConnectError("unreachable", request=request)

    with pytest.raises(llm_client.LLMCallError) as ei:
        _create(_client(handler, max_retries=2))
    msg = str(ei.value)
    assert "transient and retryable" in msg
    assert "connection error" in msg
    assert isinstance(ei.value, anthropic.APIError)


def test_server_error_is_retryable():
    def handler(_request):
        return httpx.Response(529, json=_error_json("overloaded_error", "overloaded"))

    with pytest.raises(llm_client.LLMCallError) as ei:
        _create(_client(handler, max_retries=1))
    assert "transient and retryable" in str(ei.value)
    assert "HTTP 529" in str(ei.value)


# ------------------------------------------------------- fatal request


def test_bad_request_400_is_fatal_and_not_retried():
    calls = {"n": 0}

    def handler(_request):
        calls["n"] += 1
        return httpx.Response(
            400, json=_error_json("invalid_request_error", "bad model")
        )

    with pytest.raises(llm_client.LLMCallError) as ei:
        _create(_client(handler, max_retries=4))

    assert calls["n"] == 1  # fatal: not retried despite budget=4
    msg = str(ei.value)
    assert "HTTP 400" in msg
    assert "retrying will not help" in msg
    assert "Traceback" not in msg
    assert isinstance(ei.value, anthropic.APIError)


def test_auth_401_is_fatal_and_not_retried():
    calls = {"n": 0}

    def handler(_request):
        calls["n"] += 1
        return httpx.Response(401, json=_error_json("authentication_error", "bad key"))

    with pytest.raises(llm_client.LLMCallError) as ei:
        _create(_client(handler, max_retries=4))
    assert calls["n"] == 1
    assert "retrying will not help" in str(ei.value)


# --------------------------------------------------- happy path passthrough


def test_success_is_returned_unchanged():
    def handler(_request):
        return httpx.Response(200, json=_message_json())

    resp = _create(_client(handler))
    assert resp.content[0].text == "ok"
    assert resp.usage.output_tokens == 7


# ------------------------------------------------- timeout + retry constants


def test_timeout_and_retries_are_explicit_named_constants():
    # The timeout is granular: short connect, long read for extended-thinking gens.
    assert llm_client.LLM_TIMEOUT.connect == llm_client.LLM_CONNECT_TIMEOUT_SECONDS
    assert llm_client.LLM_TIMEOUT.read == llm_client.LLM_READ_TIMEOUT_SECONDS
    assert (
        llm_client.LLM_READ_TIMEOUT_SECONDS >= 300
    )  # generous: minutes-long generations
    assert llm_client.LLM_MAX_RETRIES >= 2  # tuned above the SDK default
    c = llm_client.build_client()
    assert c.max_retries == llm_client.LLM_MAX_RETRIES
    assert c.timeout == llm_client.LLM_TIMEOUT


def test_no_fabricated_backoff_ceiling_constant():
    # The cumulative-ceiling constant enforced nothing and was numerically wrong;
    # it was removed in favor of describing the SDK's real backoff.
    assert not hasattr(llm_client, "BACKOFF_CEILING_SECONDS")


# --------------------------------------------------- model capability


@pytest.mark.parametrize(
    "model",
    [
        "claude-opus-4-8",
        "claude-opus-4-7",
        "claude-opus-4-6",
        "claude-sonnet-4-6",
    ],
)
def test_known_thinking_models_supported(model):
    assert llm_client.supports_adaptive_thinking(model) is True


@pytest.mark.parametrize(
    "model",
    [
        "claude-haiku-4-5",
        "claude-opus-4-5",
        "claude-sonnet-4-5",
    ],
)
def test_known_non_thinking_models_unsupported(model):
    assert llm_client.supports_adaptive_thinking(model) is False


@pytest.mark.parametrize(
    "model",
    [
        "claude-opus-4-9",
        "claude-opus-5-0",
        "claude-sonnet-4-7",
        "claude-fable-5",
    ],
)
def test_newer_models_keep_thinking(model):
    # A newer model in a thinking-capable family must not silently lose thinking.
    assert llm_client.supports_adaptive_thinking(model) is True


@pytest.mark.parametrize(
    "model",
    [
        "",
        None,
        "gpt-4o",
        "claude-zephyr-9",
        "claude-opus",
        "not-a-model",
    ],
)
def test_unknown_models_default_to_no_thinking(model):
    # An unknown/unparseable id must run via the conservative no-thinking path,
    # never claim a capability it may not have.
    assert llm_client.supports_adaptive_thinking(model) is False
