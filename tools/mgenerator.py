"""Phase V2 multi-file generator — one Anthropic call that rewrites a bloated
MULTI-FILE unit into a simpler one, emitted as several files and parsed back into
a candidate package directory that mevaluator.evaluate ingests directly. This is
the multi-file analogue of tools/generator.py: the loop orchestrates and the
evaluator judges; the generator only proposes.

Fork 1 (directed loop): generation 1 sees the whole original unit (every file
with its path) plus the behavior description from meta.json; generation N>1 ALSO
sees the previous candidate files and the feedback string it is handed, verbatim.
Fork 3 (honest by construction): it NEVER sees the test suite, the reference, the
breaks, or any expected outcome — only the original code and the behavior
description, so it must genuinely simplify and the evaluator verifies it.

THE NEW FAILURE SURFACE OF V2: this module parses multi-file model output and
writes model-proposed filenames to disk. Two hard guarantees follow.

1. STATIC VALIDATION ONLY. The candidate is untrusted AI code; only the v2.0
   container may run it. This module never imports, compiles, or otherwise runs
   the candidate on the host. Every check here is pure text / ast.parse analysis.

2. PATH SAFETY. Every emitted path must be relative, end in .py, and stay inside
   the candidate directory (no absolute paths, no `..` traversal). Any violation
   makes the result invalid and writes nothing, anywhere.

Malformed output is NOT fatal: prose-only output, a syntax error in any file, a
missing __init__.py, an unexposed entry class, or an unsafe path each yields an
invalid result carrying a specific, actionable error string (the loop feeds it
back next generation). Only an API failure raises. The pricing table, the model-
capability gating, and the .env key loader are reused from tools/generator.py by
import (not duplicated); the API key is read from the environment and never
hardcoded or printed.

Usage: python mgenerator.py <case_dir> <out_dir> [model]
"""
import ast
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

# Reuse generator.py's machinery by import: the pricing table, the token budget,
# the request configuration (request_kwargs -- the pinned temperature plus the
# adaptive-thinking/effort knobs), and the .env key loader. None of these are
# re-implemented here (out-of-scope rule 1).
from generator import (
    DEFAULT_MODEL as _GEN_DEFAULT_MODEL,
    MAX_TOKENS,
    PRICING,
    _load_dotenv,
    request_kwargs,
)
# The one-call hardening (client construction with the explicit timeout + retry
# budget, failure classification, and the model-capability check) is shared with
# generator via llm_client.
from llm_client import (
    build_client,
    create_message,
)
import logsetup
import runinput

log = logsetup.get_logger("mgenerator")  # operational log -> stderr (configured at the entry point)

DEFAULT_MODEL = os.environ.get("MGENERATOR_MODEL", _GEN_DEFAULT_MODEL)

SYSTEM = (
    "You are an expert Python engineer doing behavior-preserving simplification of "
    "a MULTI-FILE unit. You are given a package (several files) that exports one "
    "public class. Rewrite the WHOLE unit to be as simple, clean, and readable as "
    "possible WITHOUT changing its observable behavior at the public API for any "
    "sequence of calls.\n"
    "Rules:\n"
    "- Keep the public class name and every public method name and signature "
    "EXACTLY; preserve return values, state evolution, and exception types and "
    "messages for every input.\n"
    "- The unit MUST remain an importable package: emit an __init__.py at the unit "
    "root that exposes the public class (define it there, or import and re-export "
    "it). Submodules must use relative imports (for example `from .helpers import X`).\n"
    "- You may restructure across however many files you want, including fewer "
    "files, but every emitted file must be Python source whose path ends in .py and "
    "is relative to the unit root (no absolute paths, no `..`).\n"
    "- Remove unnecessary complexity: dead code, unused helpers/classes, redundant "
    "abstraction, unneeded dependencies, and deep nesting.\n"
    "- Do NOT add dependencies, I/O, printing, global state, or tests, and do NOT "
    "try to detect or special-case any test harness.\n"
    "- Output ONLY the rewritten files. For EACH file, emit a line "
    "`### FILE: <relative/path.py>` immediately followed by a single ```python "
    "fenced code block holding that file's full source. Emit no other prose."
)

# A `### FILE: <path>` marker line (tolerant of leading `#` heading markers and of
# the path being wrapped in backticks) followed by one fenced code block. The
# capture is plain text; the body is never compiled here.
_BLOCK_RE = re.compile(
    r"^[ \t]*#{0,6}[ \t]*FILE:[ \t]*`?(?P<path>[^\n`]+?)`?[ \t]*\n+"
    r"```[^\n]*\n(?P<code>.*?)\n?```",
    re.DOTALL | re.MULTILINE,
)


@dataclass
class MGenResult:
    files: dict           # relative-path -> source for the emitted files ({} if none)
    raw_text: str         # the model's full text response (kept for the audit log)
    valid: bool           # all files parse, __init__ exposes the entry, paths safe
    error: str | None     # why invalid (fed back as next-gen feedback); None if valid
    candidate_dir: str | None   # set iff valid AND an out_dir was given (materialized)
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    flags: list = field(default_factory=list)  # reserved; parity with the basket shape


# ---------------------------------------------------------------- prompt

def _format_unit(files):
    """Render a {path: source} map as path-labelled fenced blocks for the prompt."""
    return "\n\n".join(
        f"### FILE: {path}\n```python\n{src.rstrip()}\n```"
        for path, src in sorted(files.items())
    )


def _build_user(meta, original_files, prev_files, prev_feedback):
    entry = meta["entry"]
    api = ", ".join(meta.get("public_api", []))
    parts = [
        f"UNIT: {meta.get('kind', '').strip()}",
        f"Public class (entry point): `{entry}` — keep this class name and its "
        f"public method names and signatures EXACTLY: {api}.",
        f"Why it is stateful: {meta.get('stateful_because', '').strip()}",
        f"Constraints: {meta.get('constraints', '').strip()}",
        "",
        "Current implementation to simplify (the whole unit, each file with its path):",
        _format_unit(original_files),
    ]
    if prev_files is not None:  # generation N>1: previous attempt + feedback (Fork 1)
        parts += [
            "",
            "Your previous attempt (the whole unit you last emitted):",
            _format_unit(prev_files),
            "",
            "Evaluation of your previous attempt (this is the ONLY signal you get — "
            "you cannot see the tests, the reference, or the expected outputs):",
            prev_feedback or "(none)",
            "",
            "Produce an improved, complete unit that addresses this feedback while "
            "preserving exact behavior at the public API.",
        ]
    else:
        parts += ["", "Rewrite the unit to be as simple and clean as possible while "
                  "preserving exact behavior at the public API."]
    return "\n".join(parts)


# ---------------------------------------------------------------- parsing

def parse_emission(text):
    """Map relative-path -> source for every `### FILE:` block in the model text.

    Pure text parsing: the candidate source is never compiled or run here. A
    later-emitted duplicate path wins (last write), matching how a file map would
    settle on disk.
    """
    files = {}
    for m in _BLOCK_RE.finditer(text):
        path = m.group("path").strip().strip("`").strip().strip('"').strip("'").strip()
        files[path] = m.group("code")
    return files


# ------------------------------------------------------------ validation

def _path_error(path):
    """None if `path` is a safe relative .py path that stays inside the unit root,
    else a specific reason. Pure string analysis; touches no filesystem."""
    raw = (path or "").strip()
    if not raw:
        return "an emitted file block has an empty path."
    norm = raw.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
        return (f"path '{raw}' is absolute; every emitted path must be relative to "
                f"the unit root and stay inside it.")
    segments = [s for s in norm.split("/") if s != "" and s != "."]
    if any(s == ".." for s in segments):
        return (f"path '{raw}' uses '..' to escape the unit root; emitted paths must "
                f"stay inside the candidate directory.")
    if not norm.endswith(".py"):
        return (f"path '{raw}' does not end in .py; only Python source files may be "
                f"emitted.")
    if not segments or segments[-1] in ("..", "."):
        return f"path '{raw}' is not a valid file path."
    return None


def _exposes(init_src, entry):
    """True if `entry` is statically exposed at the top level of __init__.py:
    defined there (class/function/assignment) or imported and re-exported under
    that exact name. Static (ast) only — nothing is imported or run."""
    for node in ast.parse(init_src).body:
        if (isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == entry):
            return True
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == entry for t in node.targets):
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if (alias.asname or alias.name.split(".")[0]) == entry:
                    return True
    return False


def validate(files, entry):
    """None if the emitted file map is a safe, statically valid candidate package
    exposing `entry`; else a specific, actionable error string (the loop forwards
    it as feedback). Does no filesystem or runtime work whatsoever."""
    if not files:
        return ("your response contained no `### FILE:` blocks at all; emit each "
                "file as a `### FILE: <path.py>` marker followed by a fenced "
                "```python code block.")
    # Path safety first: a single unsafe path invalidates the whole emission, and
    # nothing is ever written for an invalid result.
    for path in sorted(files):
        err = _path_error(path)
        if err is not None:
            return err
    # Every file must parse; name the offending file on a syntax error.
    for path in sorted(files):
        try:
            ast.parse(files[path])
        except SyntaxError as e:
            return (f"file '{path}' is not valid Python: {e.__class__.__name__}: "
                    f"{e.msg} (line {e.lineno}).")
    if "__init__.py" not in files:
        return ("no __init__.py at the unit root; the candidate must be an "
                "importable package whose __init__.py exposes the entry class.")
    if not _exposes(files["__init__.py"], entry):
        return (f"__init__.py does not expose the entry class `{entry}`; define it "
                f"there or import and re-export it (for example "
                f"`from .submodule import {entry}`).")
    return None


# ----------------------------------------------------------- materialize

def materialize(files, dest):
    """Write a path->source map into `dest` as a package directory, creating parent
    directories as needed. Defense in depth: every path is re-checked for safety
    BEFORE any write, so an unsafe map raises and leaves nothing on disk."""
    for path in files:
        err = _path_error(path)
        if err is not None:
            raise ValueError(f"refusing to materialize unsafe path: {err}")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for path, src in files.items():
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(src if src.endswith("\n") else src + "\n", encoding="utf-8")
    return dest


def read_unit(unit_dir):
    """Read a package directory into a {relative-path: source} map (text only;
    nothing is compiled or run). __pycache__ is skipped. The inverse of
    materialize, used to feed the original unit to generate()."""
    unit_dir = Path(unit_dir)
    return {
        str(p.relative_to(unit_dir)).replace(os.sep, "/"): p.read_text(encoding="utf-8")
        for p in sorted(unit_dir.rglob("*.py"))
        if "__pycache__" not in p.parts
    }


# ---------------------------------------------------------------- generate

def generate(meta, original_files, prev_files=None, prev_feedback=None,
             model=DEFAULT_MODEL, client=None, out_dir=None):
    """One LLM call -> a candidate MGenResult. The candidate is parsed and STATICALLY
    validated; it is never run on the host. If the result is valid and `out_dir` is
    given, the candidate package is materialized there and candidate_dir is set; an
    invalid result writes nothing, anywhere. Raises only on an API failure (after
    the SDK's own retries); the loop treats that as the single halting condition.
    `client` is injectable (default a real Anthropic client) so the parse,
    validation, and materialize paths are testable with no API call and no key.
    """
    if client is None:
        # The key is needed only now, when constructing the real client (an
        # injected client needs neither the key nor the .env side effect). The
        # env load stays explicit at this call site; build_client does not load it.
        _load_dotenv()
        client = build_client()
    resp = create_message(
        client,
        model=model, max_tokens=MAX_TOKENS, system=SYSTEM,
        messages=[{"role": "user",
                   "content": _build_user(meta, original_files, prev_files, prev_feedback)}],
        **request_kwargs(model),
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    files = parse_emission(text)
    error = validate(files, meta["entry"])

    candidate_dir = None
    if error is None and out_dir is not None:
        candidate_dir = str(materialize(files, out_dir))

    in_rate, out_rate = PRICING.get(model, (0.0, 0.0))
    u = resp.usage
    return MGenResult(
        files=files, raw_text=text, valid=error is None, error=error,
        candidate_dir=candidate_dir, model=model,
        input_tokens=u.input_tokens, output_tokens=u.output_tokens,
        cost_usd=round(u.input_tokens * in_rate + u.output_tokens * out_rate, 6),
    )


def main():
    import sys
    if len(sys.argv) not in (3, 4):
        sys.exit("usage: python mgenerator.py <case_dir> <out_dir> [model]")
    logsetup.configure()   # entry point: wire logging once (never at import)
    case_dir = Path(sys.argv[1])
    out_dir = sys.argv[2]
    model = sys.argv[3] if len(sys.argv) == 4 else DEFAULT_MODEL
    meta = runinput.load_mcase_meta(case_dir)
    original_files = read_unit(case_dir / "original")
    r = generate(meta, original_files, model=model, out_dir=out_dir)
    result = {"valid": r.valid, "error": r.error, "files": sorted(r.files),
              "candidate_dir": r.candidate_dir, "model": r.model,
              "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
              "cost_usd": r.cost_usd}
    log.info(json.dumps(result, indent=2),
             extra={"model": r.model, "valid": r.valid,
                    "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                    "cost_usd": r.cost_usd})


# The API key is loaded by generate() (via generator._load_dotenv) at the point the
# real client is constructed, so importing this module never mutates os.environ.


if __name__ == "__main__":
    main()
