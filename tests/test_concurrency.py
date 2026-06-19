"""Concurrency safety of the evaluator's loading state (P5.4, decision 0024).

The dynamic-import names in mverify._load_corpus, validate_mcase._load_module, and
mdiffer.load_unit (the host-side original-unit load reached on the evaluation path
at mverify.check_equivalence_containerized) used to come from a module-global
counter incremented with a non-atomic read-modify-write, so two concurrent loads
could mint the SAME sys.modules name and collide. These tests load many modules
concurrently (threads, one process, all released together by a barrier to maximize
overlap on the minting) and assert NO name collision, NO exception, and each load
correct and independent. No API, no Docker, no model.

  cd tools && python -m pytest test_concurrency.py -q -p no:cacheprovider
"""

import sys
import threading

from darwin import mdiffer
from darwin import mverify
from darwin import validate_mcase


def _run_threads(targets):
    """Start every target on its own thread, released together, and join. Returns
    the list of exceptions any thread raised (empty == all clean)."""
    errors = []
    lock = threading.Lock()
    barrier = threading.Barrier(len(targets))

    def wrap(fn):
        def run():
            try:
                barrier.wait()  # all threads hit the name minting together
                fn()
            except Exception as e:  # capture, do not crash the harness thread
                with lock:
                    errors.append(repr(e))

        return run

    threads = [threading.Thread(target=wrap(fn)) for fn in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def test_load_module_concurrent_no_collision(tmp_path):
    """validate_mcase._load_module: N threads each load a DISTINCT aux module that
    encodes its own value. With the old shared counter two threads could mint the
    same name; with uuid every minted name is unique and each module is independent."""
    n = 32
    results, lock = {}, threading.Lock()

    def make(i):
        path = tmp_path / f"aux_{i}.py"
        path.write_text(f"VALUE = {i}\n", encoding="utf-8")

        def load():
            mod = validate_mcase._load_module(path)
            with lock:
                results[i] = (mod.__name__, mod.VALUE)

        return load

    errors = _run_threads([make(i) for i in range(n)])

    assert not errors, errors
    assert len(results) == n
    # Each load is correct and independent: module i sees VALUE == i.
    for i in range(n):
        assert results[i][1] == i
    # No name collision: every minted name is unique, uuid-shaped, and still
    # registered in sys.modules pointing at the right module (TASK CONSTRAINT 3).
    names = [name for name, _ in results.values()]
    assert len(set(names)) == n
    for name, val in results.values():
        assert name.startswith("mcase_aux_")
        assert name in sys.modules and sys.modules[name].VALUE == val


def test_load_corpus_concurrent_no_collision(tmp_path):
    """mverify._load_corpus: N threads each load a DISTINCT corpus.py whose
    build_corpus() returns its own marker. Asserts every result is correct and N
    new, distinct sys.modules names were registered (no collision)."""
    n = 32
    results, lock = {}, threading.Lock()
    before = {k for k in sys.modules if k.startswith("mverify_corpus_")}

    def make(i):
        case_dir = tmp_path / f"case_{i}"
        case_dir.mkdir()
        (case_dir / "corpus.py").write_text(
            f"def build_corpus():\n    return {i}\n", encoding="utf-8"
        )

        def load():
            val = mverify._load_corpus(case_dir)
            with lock:
                results[i] = val

        return load

    errors = _run_threads([make(i) for i in range(n)])

    assert not errors, errors
    # Each corpus built correctly and independently.
    assert results == {i: i for i in range(n)}
    # N new, DISTINCT sys.modules names minted (no two loads collided on a name).
    after = {k for k in sys.modules if k.startswith("mverify_corpus_")}
    assert len(after - before) == n


def test_load_unit_concurrent_no_collision(tmp_path):
    """mdiffer.load_unit: the host-side original-unit load reached on the production
    evaluation path (mverify.check_equivalence_containerized, from mevaluator.evaluate).
    N threads each load a DISTINCT package whose __init__ encodes its own value;
    asserts no name collision, no exception, and each load correct and independent."""
    n = 32
    results, lock = {}, threading.Lock()

    def make(i):
        pkg = tmp_path / f"unit_{i}"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(f"VALUE = {i}\n", encoding="utf-8")

        def load():
            mod = mdiffer.load_unit(pkg)
            with lock:
                results[i] = (mod.__name__, mod.VALUE)

        return load

    errors = _run_threads([make(i) for i in range(n)])

    assert not errors, errors
    assert len(results) == n
    # Each load is correct and independent: unit i sees VALUE == i.
    for i in range(n):
        assert results[i][1] == i
    # No name collision: every minted alias is unique, uuid-shaped, and still
    # registered in sys.modules pointing at the right module (TASK CONSTRAINT 3).
    names = [name for name, _ in results.values()]
    assert len(set(names)) == n
    for name, val in results.values():
        assert name.startswith("mcase_unit_")
        assert name in sys.modules and sys.modules[name].VALUE == val
