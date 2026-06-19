"""Compute complexity metrics for a .py file. Pure analysis, zero LLM.

Usage: python -m darwin.freeze_metrics <path.py>
Prints a JSON object with the frozen metrics to stdout.
"""

import ast
import json
import sys

from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.raw import analyze
from radon.visitors import Class
from vulture import Vulture

# Block statements that increase nesting depth. ClassDef/FunctionDef are
# included so over-abstraction (nested wrappers) shows up as deeper nesting.
NEST_NODES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ExceptHandler,
)

# Vulture reports unused functions/vars at 60 and unused imports at 90; 60
# captures all of them while filtering nothing relevant. Fixed for determinism.
VULTURE_MIN_CONFIDENCE = 60


def _leaf_functions(blocks):
    """Flatten radon blocks to every function/method, including closures."""
    for b in blocks:
        if isinstance(b, Class):
            yield from _leaf_functions(b.methods)
        else:  # Function
            yield b
            yield from _leaf_functions(b.closures)


def _max_nesting_depth(node, level=0):
    best = level
    for child in ast.iter_child_nodes(node):
        inc = 1 if isinstance(child, NEST_NODES) else 0
        best = max(best, _max_nesting_depth(child, level + inc))
    return best


def _dependencies(tree):
    deps = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                deps.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            deps.add(node.module.split(".")[0])
    return sorted(deps)


def freeze(path):
    with open(path, encoding="utf-8") as fh:
        code = fh.read()
    tree = ast.parse(code)

    comps = [f.complexity for f in _leaf_functions(cc_visit(code))]
    raw = analyze(code)
    deps = _dependencies(tree)

    v = Vulture(verbose=False)
    v.scavenge([path])
    dead = v.get_unused_code(min_confidence=VULTURE_MIN_CONFIDENCE)

    return {
        "cyclomatic_total": sum(comps),
        "cyclomatic_max": max(comps) if comps else 0,
        "maintainability_index": round(mi_visit(code, True), 2),
        "logical_loc": raw.lloc,
        "source_loc": raw.sloc,
        "dependency_count": len(deps),
        "dependencies": deps,
        "dead_code_count": len(dead),
        "max_nesting_depth": _max_nesting_depth(tree),
    }


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m darwin.freeze_metrics <path.py>")
    print(json.dumps(freeze(sys.argv[1]), indent=2))


if __name__ == "__main__":
    main()
