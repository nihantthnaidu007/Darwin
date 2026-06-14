"""Tests for the V1 containerized equivalence gate (mverify.py).

Docker required (image darwin-sandbox:py313): every candidate replay runs
inside the v2.0 container. Run from tools/:

    ../.venv/bin/python -m pytest test_mverify.py -v

Covers, per success criterion:
- each mcase's clean reference is EQUIVALENT through the container;
- one V0 planted break per case is NOT equivalent, and the reported first
  divergence matches V0's in-process mdiffer verdict exactly;
- a probing candidate observes the lockdown from inside (non-root, no
  network, read-only filesystem);
- a filesystem-dumping candidate sees only its own source, the sequence
  inputs, and the replay driver -- never the original or any outcomes;
- a candidate that cannot even import fails closed;
- batching spans partition the corpus (host-only, no Docker).
"""
import json
from pathlib import Path

import pytest

from mdiffer import check_equivalence
from mverify import _BATCH_BUDGET, _batch_spans, check_equivalence_containerized
from validate_mcase import _load_module, _materialize_break

MCASES = (Path(__file__).parent / ".." / "mcases").resolve()
CASES = sorted(p.name for p in MCASES.iterdir() if (p / "meta.json").exists())

# One corpus-caught planted break per case (from the V0 catch-test), spanning
# the deep-state and order gap classes, not just dropped validation.
PLANTED = {
    "doc_history": "order_redo_survives_set",
    "rate_limiter": "deep_clamp_overshoot",
    "task_scheduler": "order_lifo_tie_break",
}


def _entry(case):
    return json.loads((MCASES / case / "meta.json").read_text())["entry"]


def _probe_candidate(tmp_path, entry, probe_body):
    """A candidate package whose constructor raises RuntimeError carrying a
    JSON probe report: the report comes back in the divergence witness, so it
    is observably produced INSIDE the container."""
    pkg = tmp_path / "probe"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "import json, os, socket\n"
        f"class {entry}:\n"
        "    def __init__(self, *a, **k):\n"
        + probe_body +
        "        raise RuntimeError(json.dumps(report))\n",
        encoding="utf-8")
    return pkg


def _witness_report(case, candidate):
    eq, witness, _stats = check_equivalence_containerized(MCASES / case, candidate)
    assert not eq
    assert witness["candidate"][0] == "raise"
    assert witness["candidate"][1] == "RuntimeError"
    return json.loads(witness["candidate"][2])


@pytest.mark.parametrize("case", CASES)
def test_reference_is_equivalent_through_container(case):
    eq, witness, stats = check_equivalence_containerized(
        MCASES / case, MCASES / case / "reference")
    assert eq, f"clean reference rejected: {witness} {stats}"
    assert witness is None
    assert stats["container_runs"] >= 1
    assert stats["sequences"] == len(_load_module(MCASES / case / "corpus.py").build_corpus())


@pytest.mark.parametrize("case", CASES)
def test_planted_break_is_caught_with_v0_witness(case, tmp_path):
    breaks = _load_module(MCASES / case / "breaks.py").BREAKS
    brk = next(b for b in breaks if b["name"] == PLANTED[case])
    broken = _materialize_break(MCASES / case / "original", brk, tmp_path)

    eq, witness, _stats = check_equivalence_containerized(MCASES / case, broken)
    assert not eq
    assert witness is not None

    # The containerized gate must report the SAME first divergence V0's
    # in-process check reports (same corpus order, same comparison).
    corpus = _load_module(MCASES / case / "corpus.py").build_corpus()
    eq0, witness0, _ = check_equivalence(
        MCASES / case / "original", broken, corpus, entry=_entry(case))
    assert not eq0
    assert witness["sequence"] == witness0["sequence"]
    assert witness["call_index"] == witness0["call_index"]
    assert witness["call"] == witness0["call"]


def test_probe_confirms_container_lockdown(tmp_path):
    body = (
        "        report = {'uid': os.getuid(), 'gid': os.getgid()}\n"
        "        try:\n"
        "            socket.create_connection(('1.1.1.1', 53), timeout=2).close()\n"
        "            report['network'] = 'CONNECTED (BAD)'\n"
        "        except OSError as e:\n"
        "            report['network'] = 'blocked: ' + type(e).__name__\n"
        "        for label, path in (('write_sandbox', '/sandbox/x'),\n"
        "                            ('write_root', '/x')):\n"
        "            try:\n"
        "                open(path, 'w').close()\n"
        "                report[label] = 'WRITABLE (BAD)'\n"
        "            except OSError as e:\n"
        "                report[label] = 'denied: ' + type(e).__name__\n"
    )
    case = "doc_history"
    report = _witness_report(case, _probe_candidate(tmp_path, _entry(case), body))
    assert report["uid"] == 1000          # non-root
    assert report["gid"] == 1000
    assert report["network"].startswith("blocked:")
    assert report["write_sandbox"].startswith("denied:")   # ro bind mount
    assert report["write_root"].startswith("denied:")      # ro root fs


def test_dump_sees_no_original_and_no_outcomes(tmp_path):
    repo = str(MCASES.parent)
    body = (
        "        files = []\n"
        "        for base, dirs, names in os.walk('/sandbox'):\n"
        "            dirs[:] = [d for d in dirs if d != '__pycache__']\n"
        "            files += [os.path.join(base, n) for n in names]\n"
        "        report = {'sandbox_files': sorted(files),\n"
        f"                  'host_repo_visible': os.path.exists({repo!r}),\n"
        "                  'cwd': os.getcwd()}\n"
    )
    case = "doc_history"
    report = _witness_report(case, _probe_candidate(tmp_path, _entry(case), body))
    # Exactly the allowed payload: candidate source, sequence inputs, driver.
    assert report["sandbox_files"] == [
        "/sandbox/candidate/__init__.py",
        "/sandbox/corpus.py",
        "/sandbox/driver.py",
        "/sandbox/mdiffer.py",
    ]
    assert report["host_repo_visible"] is False
    assert not any("original" in f or "reference" in f or "outcome" in f
                   for f in report["sandbox_files"])


def test_broken_import_fails_closed(tmp_path):
    pkg = tmp_path / "broken"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("def broken(:\n", encoding="utf-8")
    eq, witness, stats = check_equivalence_containerized(MCASES / "doc_history", pkg)
    assert not eq
    assert witness is None
    assert stats["error"].startswith("candidate failed to replay: SyntaxError")


def test_batch_spans_partition_the_corpus():
    # ~40 KB per sequence -> multiple spans, together covering every index once.
    reference = [[["m", ["ok", ["str", "x" * 40_000]]]] for _ in range(30)]
    spans = _batch_spans(reference)
    assert len(spans) > 1
    assert spans[0][0] == 0 and spans[-1][1] == len(reference)
    assert all(a_stop == b_start for (_, a_stop), (b_start, _)
               in zip(spans, spans[1:]))
    for start, stop in spans:
        size = sum(len(json.dumps(s, separators=(",", ":")))
                   for s in reference[start:stop])
        assert stop - start == 1 or size <= _BATCH_BUDGET
