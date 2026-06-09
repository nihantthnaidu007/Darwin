"""Phase 3 generator — one Anthropic call that rewrites a module to be simpler
while preserving behavior. It is a focused API wrapper, nothing more: the loop
orchestrates and the evaluator judges; the generator only proposes.

Fork 1 (directed loop): generation 1 sees the original code + a behavior
description; generation N>1 ALSO sees the previous candidate and the evaluator's
feedback. Fork 3 (honest by construction): it NEVER sees test_suite.py or
golden_io.json / expected outputs — only the original code and the behavior
description, so it must genuinely simplify based on behavior and the evaluator
verifies it independently.

Invalid LLM output (prose-only, a syntax error, or a missing entry point) is NOT
fatal: generate() returns it as an invalid GenResult with a specific error, and
the loop feeds that error back and continues. The API key is read from the
environment (ANTHROPIC_API_KEY) and is never hardcoded or printed.
"""
import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic

DEFAULT_MODEL = os.environ.get("GENERATOR_MODEL", "claude-opus-4-8")
MAX_TOKENS = 8192    # code + adaptive-thinking tokens; well under the SDK stream guard
EFFORT = "medium"    # focused rewrite; the evaluator (not model deliberation) is the arbiter

# Adaptive thinking + the effort knob exist only on Opus 4.6+ and Sonnet 4.6;
# Haiku 4.5 and older models 400 on them. Gate the request params on capability so
# the generator stays genuinely --model-configurable instead of one-model-only.
THINKS = {"claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-4-6"}

# USD per token (input, output), from the published per-1M pricing. Used only to
# report real cost from the API's own token counts; it never affects generation.
PRICING = {
    "claude-opus-4-8":   (5.00 / 1e6, 25.00 / 1e6),
    "claude-opus-4-7":   (5.00 / 1e6, 25.00 / 1e6),
    "claude-opus-4-6":   (5.00 / 1e6, 25.00 / 1e6),
    "claude-sonnet-4-6": (3.00 / 1e6, 15.00 / 1e6),
    "claude-haiku-4-5":  (1.00 / 1e6,  5.00 / 1e6),
}

SYSTEM = (
    "You are an expert Python engineer doing behavior-preserving simplification. "
    "Given a module, rewrite it to be as simple, clean, and readable as possible "
    "WITHOUT changing its observable behavior for any input.\n"
    "Rules:\n"
    "- Keep the entry-point function's name and signature EXACTLY; preserve its "
    "return values and edge-case handling for every input.\n"
    "- Remove unnecessary complexity: dead code, unused helpers/classes, redundant "
    "abstraction, unneeded imports/dependencies, and deep nesting.\n"
    "- Do NOT add dependencies, I/O, printing, global state, or tests, and do NOT "
    "try to detect or special-case any test harness.\n"
    "- Output ONLY the rewritten module as a single ```python code block."
)


@dataclass
class GenResult:
    code: str | None        # extracted candidate source (None only if nothing extractable)
    raw_text: str           # the model's full text response (kept for the audit log)
    valid: bool             # parses AND defines the entry point at module level
    error: str | None       # why invalid (fed back as next-gen feedback); None if valid
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


def _build_user(meta, original_code, prev_code, prev_feedback):
    ep = meta["entry_point"]
    parts = [
        f"TASK: {meta.get('description', '').strip()}",
        f"Constraints: {meta.get('constraints', '').strip()}",
        f"The entry point is `{ep}`; keep its name and signature unchanged.",
        "",
        "Current implementation to simplify:",
        f"```python\n{original_code.rstrip()}\n```",
    ]
    if prev_code is not None:  # generation N>1: add the previous attempt + feedback (Fork 1)
        parts += [
            "",
            "Your previous attempt:",
            f"```python\n{prev_code.rstrip()}\n```",
            "",
            "Evaluation of your previous attempt (this is the ONLY signal you get — "
            "you cannot see the tests or the expected outputs):",
            prev_feedback or "(none)",
            "",
            "Produce an improved, complete module that addresses this feedback while "
            "preserving exact behavior.",
        ]
    else:
        parts += ["", "Rewrite it to be as simple and clean as possible while "
                  "preserving exact behavior."]
    return "\n".join(parts)


def _extract_code(text):
    """Pull the first fenced code block; fall back to the whole text if unfenced."""
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    return (blocks[0].strip() if blocks else text.strip()) or None


def _validate(code, entry_point):
    """None if the code parses and defines `entry_point` at module level; else a
    specific, actionable error string (the loop forwards it as feedback)."""
    if code is None:
        return "your response contained no code at all."
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return (f"your output was not valid Python: {e.__class__.__name__}: "
                f"{e.msg} (line {e.lineno}).")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entry_point:
            return None
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == entry_point for t in node.targets):
            return None
    return f"your module did not define the required entry point `{entry_point}` at module level."


def generate(meta, original_code, prev_code=None, prev_feedback=None,
             model=DEFAULT_MODEL, client=None):
    """One LLM call -> a candidate GenResult. Raises only on an API failure (after
    the SDK's own retries); the loop treats that as the single halting condition."""
    client = client or anthropic.Anthropic()
    extra = ({"thinking": {"type": "adaptive"}, "output_config": {"effort": EFFORT}}
             if model in THINKS else {})
    resp = client.messages.create(
        model=model, max_tokens=MAX_TOKENS, system=SYSTEM,
        messages=[{"role": "user",
                   "content": _build_user(meta, original_code, prev_code, prev_feedback)}],
        **extra,
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    code = _extract_code(text)
    error = _validate(code, meta["entry_point"])
    in_rate, out_rate = PRICING.get(model, (0.0, 0.0))
    u = resp.usage
    return GenResult(code, text, error is None, error, model,
                     u.input_tokens, u.output_tokens,
                     round(u.input_tokens * in_rate + u.output_tokens * out_rate, 6))


# --- API key from the environment (never hardcoded/printed) -----------------
def _load_dotenv():
    """If ANTHROPIC_API_KEY isn't already exported, load it from the project .env
    (gitignored). Existing env vars win; values are never logged."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()
