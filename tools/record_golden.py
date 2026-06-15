"""Record golden input/output pairs from a clean reference .py.

Calls <entry_point> on each argument set and freezes the results so later
candidates can be checked for behavioral identity.

Usage: python record_golden.py <reference.py> <entry_point> <arg_sets.json> [-o out.json]

arg_sets.json holds a JSON list. Each element is either a list (positional
args) or an object {"args": [...], "kwargs": {...}}.

Output JSON: {"entry_point": ..., "cases": [{"args", "kwargs", "output"}, ...]}
"""
import importlib.util
import json
import sys


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize(value):
    """JSON round-trip so tuples->lists etc. compare consistently later."""
    return json.loads(json.dumps(value))


def _split(arg_set):
    if isinstance(arg_set, list):
        return arg_set, {}
    return arg_set.get("args", []), arg_set.get("kwargs", {})


def record(reference_path, entry_point, arg_sets):
    fn = getattr(_load(reference_path, "reference"), entry_point)
    cases = []
    for arg_set in arg_sets:
        args, kwargs = _split(arg_set)
        output = fn(*args, **kwargs)
        cases.append({
            "args": _normalize(args),
            "kwargs": _normalize(kwargs),
            "output": _normalize(output),
        })
    return {"entry_point": entry_point, "cases": cases}


def main():
    if len(sys.argv) not in (4, 6):
        sys.exit("usage: python record_golden.py <reference.py> <entry_point> "
                 "<arg_sets.json> [-o out.json]")
    ref, entry, arg_file = sys.argv[1:4]
    arg_sets = json.load(open(arg_file, encoding="utf-8"))
    golden = record(ref, entry, arg_sets)
    text = json.dumps(golden, indent=2)
    if len(sys.argv) == 6 and sys.argv[4] == "-o":
        with open(sys.argv[5], "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
