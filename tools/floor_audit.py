"""
Corpus-wide floor audit for Darwin single-function cases.
Reads every cases/<name>/baseline_metrics.json and reports:
  1. The floor-to-original gap on the weighted basket (small gap = weak bloat or tight floor)
  2. Whether the reference itself is suspiciously small (could be pre-floor)

Usage (from repo root):
  PYTHONPATH=src python tools/floor_audit.py

Requires: radon, vulture installed in the active venv.
"""
import ast, glob, json, os, sys
from pathlib import Path
from radon.complexity import cc_visit
from radon.raw import analyze
from radon.visitors import Class
from vulture import Vulture

NEST=(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.If,ast.For,ast.AsyncFor,
      ast.While,ast.With,ast.AsyncWith,ast.Try,ast.ExceptHandler)
def _leaf(bs):
    for b in bs:
        if isinstance(b,Class): yield from _leaf(b.methods)
        else: yield b; yield from _leaf(b.closures)
def _nest(n,l=0):
    best=l
    for c in ast.iter_child_nodes(n): best=max(best,_nest(c,l+(1 if isinstance(c,NEST) else 0)))
    return best
def _deps(t):
    d=set()
    for n in ast.walk(t):
        if isinstance(n,ast.Import):
            for x in n.names: d.add(x.name.split(".")[0])
        elif isinstance(n,ast.ImportFrom) and n.level==0 and n.module: d.add(n.module.split(".")[0])
    return sorted(d)
def freeze(path):
    code=open(path,encoding="utf-8").read(); t=ast.parse(code)
    comps=[f.complexity for f in _leaf(cc_visit(code))]; raw=analyze(code)
    v=Vulture(verbose=False); v.scavenge([path])
    return {"cyc":sum(comps),"cmax":max(comps) if comps else 0,"loc":raw.lloc,
            "nest":_nest(t),"dep":len(_deps(t)),"dead":len(v.get_unused_code(min_confidence=60))}
W={"cyc":3.0,"loc":2.0,"nest":1.0,"dep":1.0,"dead":1.0,"cmax":0.5}
def wc(m): return round(sum(W[k]*m[k] for k in W),1)

cases_dir=Path("cases")
if not cases_dir.exists():
    sys.exit("Run from repo root (cases/ not found)")

rows=[]
for meta_f in sorted(cases_dir.glob("*/meta.json")):
    case_dir=meta_f.parent
    name=case_dir.name
    meta=json.loads(meta_f.read_text())
    bm=json.loads((case_dir/"baseline_metrics.json").read_text())
    orig=bm["original"]; floor=bm["reference_floor"]
    ref_path=case_dir/"reference.py"
    live=freeze(str(ref_path))
    orig_w=wc({"cyc":orig["cyclomatic_total"],"cmax":orig["cyclomatic_max"],
               "loc":orig["logical_loc"],"nest":orig["max_nesting_depth"],
               "dep":orig["dependency_count"],"dead":orig["dead_code_count"]})
    floor_w=wc({"cyc":floor["cyclomatic_total"],"cmax":floor["cyclomatic_max"],
                "loc":floor["logical_loc"],"nest":floor["max_nesting_depth"],
                "dep":floor["dependency_count"],"dead":floor["dead_code_count"]})
    live_w=wc(live)
    gap=round(orig_w-floor_w,1)
    drift=round(live_w-floor_w,1)
    flags=[]
    if gap < 10: flags.append("WEAK-BLOAT(gap<10)")
    if live.get("dead",1) > 1: flags.append(f"ACCIDENTAL-DEAD(dead={live['dead']})")
    if abs(drift) > 1: flags.append(f"REFERENCE-DRIFTED(live={live_w},frozen={floor_w})")
    rows.append({"name":name,"cat":meta.get("category","?"),"diff":meta.get("difficulty","?"),
                 "floor_w":floor_w,"orig_w":orig_w,"live_w":live_w,"gap":gap,"drift":drift,"flags":flags})

print(f"{'case':<22} {'cat':<26} {'diff':<7} {'floor':>6} {'orig':>6} {'gap':>6} {'flags'}")
print("-"*100)
any_flag=False
for r in rows:
    fs=", ".join(r["flags"]) if r["flags"] else "ok"
    marker=" <-- REVIEW" if r["flags"] else ""
    print(f"{r['name']:<22} {r['cat']:<26} {r['diff']:<7} {r['floor_w']:>6} {r['orig_w']:>6} {r['gap']:>6}   {fs}{marker}")
    if r["flags"]: any_flag=True

print()
if any_flag:
    print("FLAGGED CASES REQUIRE REVIEW before new authoring.")
else:
    print("All cases pass the automated floor-audit checks.")
