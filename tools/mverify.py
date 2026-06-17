"""Containerized differential equivalence check for a candidate multi-file unit.

This is the v3 / V1 equivalence gate. V0's in-process check (mdiffer.py via
validate_mcase.py) trusts both units; here the CANDIDATE is untrusted
AI-generated code, so it executes inside the v2.0 locked-down container
(sandbox_container.py) while the ORIGINAL is replayed in this trusted host
process and the comparison happens on the host. Only WHERE the candidate runs
changes: the equivalence semantics, sequence replay, canonicalization, and
witness shape are mdiffer's, reused, not reimplemented.

Information flow across the boundary (the Phase I1 pattern from verify_case.py):
INTO the container go only the candidate source (under candidate/), the case's
corpus.py (the sequence inputs, in their deterministic seeded generator form --
stdlib-only, so host and container build bit-identical sequences: the host that
replays the original may be any of CPython 3.12 to 3.14, verified byte-identical
in canonical equivalence outcomes across that range for all three mcases, while
the sandbox container stays pinned to 3.13), mdiffer.py (the replay +
canonicalization machinery the in-container driver reuses; it contains no case
data), and the generated driver.py. The
reference outcomes, the original source, and the comparison NEVER enter the
container. The driver replays each batch sequence against the candidate on
fresh instances and emits one token-framed frame of per-call canonical
outcomes (mdiffer.canon_outcome: return value, or exception type name +
message, under the case typed-equality conventions -- True is not 1, list
order observable, dict key order not observable). The host replays the
original with mdiffer, canonicalizes the same way, and compares per call in
corpus order; the first divergence is reported in mdiffer's witness shape
{sequence, call_index, call, original, candidate}, with the two outcomes in
canon() form (the comparison domain -- the candidate's raw values exist only
inside the container).

BATCHING: sandbox_container.run() reads back at most 1,000,000 bytes of
container stdout (used as-is per V1 scope), and a full-corpus emission
measures 710-929 KB per case. Sequences are therefore split into contiguous
spans whose reference-sized payload stays under _BATCH_BUDGET bytes, one
container run per span (~4x headroom each for a divergent candidate's larger
outcomes). Comparison still walks corpus order and stops at the first
divergence, so later spans are never run and the witness is the corpus-global
first divergence.

FAIL CLOSED: a candidate that cannot be loaded or replayed (import error,
missing public method), or whose result frame is missing, duplicated,
unparseable, or not matching the batch, is NOT equivalent -- the verdict
carries the failure reason in stats["error"] and no witness, since there is
no per-call divergence to point at.

THE FORGERY BOUNDARY (carried from v2.0 / Phase I1 -- documented here, NOT
re-solved). The candidate and the driver share ONE process inside the
container, exactly as in verify_case.py. The container closes ACCESS: host
filesystem, network, secrets, and the oracle (the original and the reference
outcomes never enter the container, so there is no answer key to read). It
does NOT split the process, so a candidate can still forge the outcomes it
emits in-process: the PEP 667 frame-locals serializer hijack demonstrated in
v2.0 Phase I1 (walk the stack to the driver frame, overwrite its _dumps local
with a hardcoded-answer lambda), or compute-and-lie. This is the SAME open
boundary v2.0 ships with (see SECURITY.md, verify_case.py, and the pinned
xfail in test_behavior_gate_limits.py). It matters only if the equivalence
verdict becomes a third-party-trusted artifact (a leaderboard, a
certification, a multi-tenant service); for single-user optimization the v1
and I2 reward-hack audits found the optimizer never approaches forgery. One
nuance carried verbatim from I1: the "forgery is optimizer-disincentivized
because it adds complexity" argument holds only for compute-and-lie -- the
frame-locals hijack is hardcoded-cheap, and what stands against it today is
the trigger condition plus those empirical audits, not a complexity penalty.
Closing the residual requires the architecture change already on the roadmap
(splitting the trusted emitter out of the candidate's process); that is
deliberately NOT attempted here, and no in-process anti-forgery scheme is
added beyond the I1 driver pattern this module reuses.

Usage: python mverify.py <case_dir> <candidate_unit_dir>
Prints EQUIVALENT or NOT EQUIVALENT (+ first divergence) and exits 0 / 1.
"""
import importlib.util
import json
import secrets
import sys
import uuid
from pathlib import Path

import logsetup
import runinput
import sandbox_container as sandbox
from mdiffer import canon_outcome, load_unit, run_sequence

log = logsetup.get_logger("mverify")  # operational log -> stderr (configured at the entry point)

TOOLS = Path(__file__).parent.resolve()

# Reference-sized canonical payload allowed per container run. The hard limit is
# sandbox_container._MAX_OUTPUT (1 MB read-back per stream, used as-is); 250 KB
# of reference payload leaves ~4x headroom for a divergent candidate's larger
# emission. A frame that still overflows the cap fails closed below.
_BATCH_BUDGET = 250_000

# mdiffer's padding for length-mismatched outcome lists, in the JSON-normalized
# form the comparison below operates on.
_ABSENT = ["<absent>", ["<absent>"]]


def _load_corpus(case_dir):
    # Unique per call with NO shared counter: a uuid is collision-free without
    # coordination, so concurrent loads cannot collide on a sys.modules name
    # (decision 0024). The module is still registered in sys.modules as before.
    name = f"mverify_corpus_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, Path(case_dir) / "corpus.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.build_corpus()


def _unit_files(candidate_dir):
    """The candidate's source tree as container files under candidate/."""
    candidate_dir = Path(candidate_dir)
    return {
        f"candidate/{path.relative_to(candidate_dir)}":
            path.read_text(encoding="utf-8")
        for path in sorted(candidate_dir.rglob("*.py"))
        if "__pycache__" not in path.parts
    }


# The trusted in-container replay driver, same emission pattern as
# verify_case._golden_driver (Phase I1): bind os.write/json.dumps and load the
# trusted replay machinery BEFORE the untrusted candidate import, keep them as
# frame-locals inside _run(), emit ONE token-framed frame with a raw os.write
# to a pre-dup'ed fd, then os._exit(0). Same known-open residual too: see THE
# FORGERY BOUNDARY in the module docstring -- this raises the bar for naive
# cheats; it is NOT forgery-proof and is not meant to be.
def _unit_driver(entry, start, stop, token):
    return (
        "import json, os\n"
        "def _run():\n"
        "    _write, _dumps, _fd = os.write, json.dumps, os.dup(1)\n"
        "    import mdiffer, corpus\n"
        f"    batch = corpus.build_corpus()[{start}:{stop}]\n"
        "    try:\n"
        f"        cls = getattr(mdiffer.load_unit('candidate'), {entry!r})\n"
        "        payload = [[name, [[m, mdiffer.canon_outcome(o)]\n"
        "                           for m, o in mdiffer.run_sequence(cls, ctor, calls)]]\n"
        "                   for name, ctor, calls in batch]\n"
        "        frame = {'sequences': payload}\n"
        "    except BaseException as e:\n"
        "        frame = {'error': type(e).__name__ + ': ' + str(e)}\n"
        # Compact separators keep the emission the same size _batch_spans
        # budgeted with (it measures compact JSON), preserving the headroom.
        f"    _write(_fd, ('\\n' + {token!r}\n"
        "               + _dumps(frame, separators=(',', ':')) + '\\n').encode())\n"
        "    os._exit(0)\n"
        "_run()\n"
    )


def _extract_frame(stdout, token):
    """Read the driver's result frame; fail CLOSED unless EXACTLY ONE
    token-prefixed parseable frame is present (same rule as verify_case)."""
    frames = [line[len(token):] for line in stdout.splitlines()
              if line.startswith(token)]
    if len(frames) != 1:
        return None
    try:
        frame = json.loads(frames[0])
    except ValueError:
        return None
    return frame if isinstance(frame, dict) else None


def _canon_norm(method, outcome):
    """mdiffer's canonical outcome, JSON-round-tripped so host-side tuples
    compare equal to the candidate's JSON-decoded lists."""
    return json.loads(json.dumps([method, canon_outcome(outcome)]))


def _batch_spans(reference):
    """Contiguous (start, stop) sequence spans whose reference payload stays
    under _BATCH_BUDGET bytes (a lone oversized sequence gets its own span)."""
    spans = []
    start, size = 0, 0
    for i, seq in enumerate(reference):
        seq_size = len(json.dumps(seq, separators=(",", ":")))
        if i > start and size + seq_size > _BATCH_BUDGET:
            spans.append((start, i))
            start, size = i, 0
        size += seq_size
    spans.append((start, len(reference)))
    return spans


def check_equivalence_containerized(case_dir, candidate_dir, timeout=30.0):
    """Differential verdict with the candidate inside the container.

    Returns (equivalent, witness, stats) in mdiffer.check_equivalence's shape;
    stats gains "container_runs" and, on a fail-closed run, "error".
    """
    case_dir = Path(case_dir)
    entry = runinput.load_mcase_meta(case_dir)["entry"]
    sequences = _load_corpus(case_dir)

    # The trusted original replays HERE on the host, via mdiffer, unchanged.
    orig_cls = getattr(load_unit(case_dir / "original"), entry)
    reference = [[_canon_norm(m, o) for m, o in run_sequence(orig_cls, ctor, calls)]
                 for _name, ctor, calls in sequences]

    base_files = {
        **_unit_files(candidate_dir),
        "mdiffer.py": (TOOLS / "mdiffer.py").read_text(encoding="utf-8"),
        "corpus.py": (case_dir / "corpus.py").read_text(encoding="utf-8"),
    }

    calls_compared = 0
    runs = 0
    for span_start, span_stop in _batch_spans(reference):
        token = secrets.token_hex(16)
        files = {**base_files,
                 "driver.py": _unit_driver(entry, span_start, span_stop, token)}
        res = sandbox.run(files, ["python", "driver.py"], timeout)
        runs += 1
        stats = {"calls_compared": calls_compared, "sequences": len(sequences),
                 "container_runs": runs}

        if res.status != sandbox.OK:
            detail = res.stdout.strip() or res.stderr.strip() or res.status
            stats["error"] = f"candidate replay {res.status}: {detail[:500]}"
            return False, None, stats
        frame = _extract_frame(res.stdout, token)
        if frame is None:
            stats["error"] = ("candidate replay produced no verifiable result "
                              "frame (missing, duplicated, or unparseable)")
            return False, None, stats
        if "error" in frame:
            stats["error"] = f"candidate failed to replay: {frame['error']}"
            return False, None, stats
        emitted = frame.get("sequences")
        if not (isinstance(emitted, list) and len(emitted) == span_stop - span_start
                and all(isinstance(e, list) and len(e) == 2 and isinstance(e[1], list)
                        for e in emitted)
                and [e[0] for e in emitted]
                    == [s[0] for s in sequences[span_start:span_stop]]):
            stats["error"] = "candidate replay frame does not match the batch"
            return False, None, stats

        for offset, seq_idx in enumerate(range(span_start, span_stop)):
            name, _ctor, calls = sequences[seq_idx]
            ref_calls = reference[seq_idx]
            cand_calls = emitted[offset][1]
            for idx in range(max(len(ref_calls), len(cand_calls))):
                oa = ref_calls[idx] if idx < len(ref_calls) else _ABSENT
                ob = cand_calls[idx] if idx < len(cand_calls) else _ABSENT
                calls_compared += 1
                if oa != ob:
                    witness = {
                        "sequence": name,
                        "call_index": idx,
                        "call": "__init__" if idx == 0 else repr(calls[idx - 1]),
                        "original": oa[1],
                        "candidate": ob[1],
                    }
                    return False, witness, {"calls_compared": calls_compared,
                                            "sequences": len(sequences),
                                            "container_runs": runs}
    return True, None, {"calls_compared": calls_compared,
                        "sequences": len(sequences), "container_runs": runs}


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: python mverify.py <case_dir> <candidate_unit_dir>")
    logsetup.configure()   # entry point: wire logging once (never at import)
    eq, witness, stats = check_equivalence_containerized(sys.argv[1], sys.argv[2])
    log.info("%s (%s calls compared, %s sequences, %s container runs)",
             "EQUIVALENT" if eq else "NOT EQUIVALENT", stats["calls_compared"],
             stats["sequences"], stats["container_runs"],
             extra={"equivalent": eq, "calls_compared": stats["calls_compared"],
                    "sequences": stats["sequences"],
                    "container_runs": stats["container_runs"]})
    if witness:
        log.info("  first divergence: seq=%s call#%s %s",
                 witness["sequence"], witness["call_index"], witness["call"])
        log.info("    original : %s", witness["original"])
        log.info("    candidate: %s", witness["candidate"])
    if "error" in stats:
        log.warning("  error: %s", stats["error"], extra={"error": stats["error"]})
    sys.exit(0 if eq else 1)


if __name__ == "__main__":
    main()
