"""Shared hardening for the single Anthropic call that both generators make.

This module is the ONE place that owns three concerns, imported by both
tools/generator.py and tools/mgenerator.py so neither duplicates them:

1. Client construction with an explicit, bounded timeout and an explicit,
   tuned retry budget (build_client / the LLM_* constants below).
2. The error taxonomy: create_message() wraps client.messages.create and turns
   any SDK failure into one clear, actionable LLMCallError instead of letting a
   raw SDK stack trace surface, classifying retryable (transient) failures apart
   from fatal (the request itself is wrong) ones.
3. Model capability: supports_adaptive_thinking() derives, from the model id,
   whether adaptive thinking + the effort knob may be sent, defaulting unknown
   models to the conservative no-thinking path rather than a fixed enumeration.

Retry/backoff is handled by exactly one mechanism — the SDK's own. The Anthropic
SDK already retries connection errors, 408/409/429, and >=500 with exponential
backoff, jitter, and Retry-After handling; we set max_retries to a tuned value
and document the resulting ceiling rather than hand-rolling a second loop that
would duplicate the SDK and risk dropping Retry-After.
"""
import re

import anthropic
import httpx

# --- Timeout -----------------------------------------------------------------
# Granular by design. An extended-thinking code generation (adaptive thinking +
# effort, up to the generators' MAX_TOKENS of output) can legitimately run for
# minutes, so the READ timeout is generous: 600s (the SDK's own default ceiling)
# leaves ample headroom for a slow-but-valid generation while still bounding a
# silent hang. The CONNECT timeout is short: establishing a socket should take
# well under 10s, so failing fast here turns a dead or unreachable endpoint into
# a prompt retryable error (letting the retry budget engage) instead of stalling
# for the full read budget on a connection that will never produce bytes.
LLM_CONNECT_TIMEOUT_SECONDS = 10.0
LLM_READ_TIMEOUT_SECONDS = 600.0
LLM_TIMEOUT = httpx.Timeout(LLM_READ_TIMEOUT_SECONDS, connect=LLM_CONNECT_TIMEOUT_SECONDS)

# --- Retries + backoff ceiling ----------------------------------------------
# Tuned above the SDK default of 2 so a brief blip (a couple of 429s, or a
# transient 5xx during a deploy) is ridden out automatically, without retrying
# so persistently that a real outage stalls the loop for long. The SDK retries
# only connection errors, 408/409/429, and >=500.
LLM_MAX_RETRIES = 4

# Documented backoff ceiling (the SDK does the actual backoff; we do not add a
# second loop). The SDK sleeps min(0.5 * 2**n, 8.0) seconds before retry n,
# minus up to 25% jitter, and honors Retry-After (up to 60s) when present. With
# LLM_MAX_RETRIES=4 the four inter-attempt sleeps are ~1s + 2s + 4s + 8s, so the
# cumulative backoff is bounded at roughly 15s (jitter only lowers it; a server
# Retry-After header can extend an individual wait up to the SDK's 60s cap).
BACKOFF_CEILING_SECONDS = 15


def build_client():
    """Construct a real Anthropic client with the explicit timeout and retry
    budget above. The API key is resolved by the SDK from the environment
    (ANTHROPIC_API_KEY); callers load it via generator._load_dotenv() first."""
    return anthropic.Anthropic(timeout=LLM_TIMEOUT, max_retries=LLM_MAX_RETRIES)


# --- Error taxonomy ----------------------------------------------------------

class LLMCallError(anthropic.APIError):
    """A classified, human-actionable generation failure.

    Subclasses anthropic.APIError on purpose: both loops already treat
    `except anthropic.APIError` as their single halting condition, so raising
    this keeps that contract intact while replacing the raw SDK exception text
    with a clear message that says whether the failure is transient or fatal and
    what to do about it.
    """

    def __init__(self, message, *, request=None, body=None):
        super().__init__(message, request, body=body)


def _is_retryable_status(status):
    """The HTTP statuses the SDK itself retries. Reaching create_message with one
    of these means the retry budget is already exhausted. 529 (overloaded) is
    covered by the >= 500 arm."""
    return status in (408, 409, 429) or status >= 500


def _retryable(what, e):
    return LLMCallError(
        f"Anthropic generation failed after {LLM_MAX_RETRIES} automatic retries: "
        f"{what}. This is transient and retryable (the client already applied "
        f"exponential backoff with jitter, cumulative ceiling ~{BACKOFF_CEILING_SECONDS}s, "
        f"honoring Retry-After); retry the run later or check "
        f"https://status.anthropic.com. Underlying SDK error -> {type(e).__name__}: {e}",
        request=getattr(e, "request", None),
    )


def _fatal(e):
    kind = getattr(e, "type", None) or "request_error"
    return LLMCallError(
        f"Anthropic rejected the request as invalid (HTTP {e.status_code} {kind}): "
        f"retrying will not help. Fix the request (model id, parameters, or "
        f"credentials) before rerunning. Underlying SDK error -> "
        f"{type(e).__name__}: {e}",
        request=getattr(e, "request", None),
    )


def create_message(client, **kwargs):
    """client.messages.create with explicit failure classification.

    The SDK applies its configured retries+backoff before any exception reaches
    here, so a caught error is terminal: either a retryable condition whose
    budget is spent, or a fatal request error. Both raise a single LLMCallError
    carrying a clear, actionable message — never a raw SDK stack trace. A
    successful call is returned unchanged, so the happy path is untouched.
    """
    try:
        return client.messages.create(**kwargs)
    except anthropic.APIConnectionError as e:  # includes APITimeoutError; carries no status
        what = (f"the request exceeded the {LLM_READ_TIMEOUT_SECONDS:.0f}s read timeout"
                if isinstance(e, anthropic.APITimeoutError)
                else "the API could not be reached (connection error)")
        raise _retryable(what, e) from e
    except anthropic.APIStatusError as e:  # carries an HTTP status code
        if _is_retryable_status(e.status_code):
            raise _retryable(f"the API returned a transient HTTP {e.status_code}", e) from e
        raise _fatal(e) from e
    except anthropic.APIError as e:  # any other SDK-level API error
        raise _retryable("the API call failed", e) from e


# --- Model capability --------------------------------------------------------
# Capability is derived from the model id, not enumerated as a fixed model set,
# so an unknown OR newer model neither silently loses adaptive thinking nor
# hard-fails on a 400. Rule:
#   * families whose every released model has always-on adaptive thinking
#     (Fable / Mythos) -> supported;
#   * families that gained adaptive thinking + the effort knob at a known
#     (major, minor) and keep it in every later release (Opus 4.6+, Sonnet 4.6+)
#     -> supported at or above that version, so a future Opus/Sonnet still gets it;
#   * everything else — Haiku, pre-4.6 Opus/Sonnet, an unrecognized family, or an
#     unparseable id — takes the conservative no-thinking path, which runs without
#     claiming a capability the model may not support.
_MODEL_RE = re.compile(r"^claude-(?P<family>[a-z]+)-(?P<major>\d+)(?:[-.](?P<minor>\d+))?")
_ALWAYS_THINKING_FAMILIES = {"fable", "mythos"}
_THINKING_SINCE = {"opus": (4, 6), "sonnet": (4, 6)}


def supports_adaptive_thinking(model):
    """True iff `model` may be sent adaptive thinking + the effort knob; False
    (the safe default) for any unknown, older, or unparseable model id."""
    m = _MODEL_RE.match(model or "")
    if not m:
        return False
    family = m.group("family")
    if family in _ALWAYS_THINKING_FAMILIES:
        return True
    since = _THINKING_SINCE.get(family)
    if since is None:
        return False
    version = (int(m.group("major")), int(m.group("minor") or 0))
    return version >= since
