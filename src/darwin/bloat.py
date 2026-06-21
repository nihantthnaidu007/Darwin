"""Ask Claude to produce a needlessly complex but behavior-identical version of
a clean reference .py. This is the ONLY tool that uses an LLM.

Key resolution and the API call follow the shared convention generate() uses:
when no client is injected, bloat() loads ANTHROPIC_API_KEY from the environment
(or the gitignored project .env) via generator._load_dotenv(), constructs the
hardened client via llm_client.build_client() (explicit timeout + retry budget),
and issues the call through llm_client.create_message() (which classifies any SDK
failure into the LLMCallError taxonomy). The key is never hardcoded, logged, or
printed. bloat keeps its OWN request shape (its SYSTEM/USER prompts, max_tokens,
and adaptive thinking); it deliberately does not adopt generator's temperature or
request_kwargs.

Usage: python -m darwin.bloat <reference.py> [-o original.py]
"""

import sys

# Reuse the shared LLM-call machinery by import (the same way mgenerator does), so
# bloat does not reimplement key loading, client construction, or the call/taxonomy.
from darwin.generator import _load_dotenv
from darwin.llm_client import build_client, create_message

MODEL = "claude-opus-4-8"

SYSTEM = """You rewrite clean Python into a needlessly complex but BEHAVIORALLY \
IDENTICAL version, for a benchmark that later tries to simplify it back.

Hard requirements:
- Keep every public function's NAME and SIGNATURE byte-for-byte identical.
- Identical behavior for all inputs: same return values, same exceptions. Do NOT
  change what the code computes.
- Stay deterministic and pure: no randomness, no time, no I/O, no network, no
  global mutable state. (The reference already obeys this; keep it that way.)

Make it worse in as many of these ways as fit naturally:
- unnecessary imports / dependencies
- over-abstraction (pointless classes, wrappers, indirection)
- duplicated logic
- dead code (unused helpers, variables, branches)
- deeper nesting than needed
- verbose, roundabout patterns instead of idiomatic ones

Return ONLY the resulting Python source. No markdown fences, no commentary."""

USER = """Rewrite this reference module to be needlessly complex while keeping \
its behavior and public function signatures identical:

```python
{code}
```"""


def _strip_fences(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip() + "\n"


def bloat(reference_path, client=None):
    with open(reference_path, encoding="utf-8") as fh:
        code = fh.read()
    if client is None:
        # The key is needed only now, when constructing the real client (an
        # injected client needs neither the key nor the .env side effect). The
        # env load stays explicit at this call site; build_client does not load it.
        _load_dotenv()
        client = build_client()
    resp = create_message(
        client,
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        messages=[{"role": "user", "content": USER.format(code=code)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return _strip_fences(text)


def main():
    if len(sys.argv) not in (2, 4):
        sys.exit("usage: python -m darwin.bloat <reference.py> [-o original.py]")
    bloated = bloat(sys.argv[1])
    if len(sys.argv) == 4 and sys.argv[2] == "-o":
        with open(sys.argv[3], "w", encoding="utf-8") as fh:
            fh.write(bloated)
    else:
        print(bloated, end="")


if __name__ == "__main__":
    main()


# Note: _load_dotenv() is invoked explicitly inside bloat() at the point the real
# client is constructed — importing this module must not mutate os.environ.
