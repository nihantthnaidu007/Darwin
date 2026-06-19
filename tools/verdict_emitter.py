"""The verdict-emission seam (P6.4.2, decision 0032).

ONE typed component the 2.0 out-of-process emitter drops into by replacement,
nothing speculative beyond that. The verdict is produced and consumed in-process
today, which is fine for the single-user-trusted 1.0 posture but is the A1
in-process-forgery surface for a multi-tenant 2.0. This module makes the producer
a swap point WITHOUT changing any 1.0 behavior:

  * VerdictEmitter -- a typing.Protocol with a single method, emit(case_dir,
    candidate_dir, timeout) -> MEvaluation. The single seam between the loop and
    the verdict producer.
  * InProcessEmitter -- the ONLY shipped implementation. Its emit() produces the
    verdict in THIS process by delegating to mevaluator.evaluate. It WRAPS
    evaluate(); it reimplements no gate, scoring, or equivalence logic. This is the
    1.0 default and is byte-identical to calling evaluate() directly.

The verdict (mevaluator.MEvaluation) is serializable (MEvaluation.to_dict /
from_dict), so a 2.0 emitter can run evaluate() across a process boundary and hand
the same typed MEvaluation back. Because mloop.run_loop and mbenchmark.run_benchmark
depend only on a VerdictEmitter, that 2.0 emitter swaps in by replacing this one
component, touching no consumer.

ONE protocol, ONE implementation: no registry, factory, plugin system, config-driven
selection, second implementation, or out-of-process implementation is built here. The
out-of-process emitter is RECEIVED in 2.0, it is not built now. The only other
emitter that exists is the test fake in the seam tests (tools/test_verdict_emitter.py),
which is not shipped.

Trust posture (SECURITY.md, decision 0008): the in-process default is acceptable at
1.0 because forging one's own optimization verdict is pointless under the
single-user-trusted posture; multi-tenant 2.0 needs the out-of-process emitter for
forgery resistance. A1 in-process verdict forgery is open-by-design at 1.0 (the two
decision-0008 xfail vectors in tools/test_behavior_gate_limits.py).
"""

from typing import Protocol, runtime_checkable

from mevaluator import MEvaluation, evaluate


@runtime_checkable
class VerdictEmitter(Protocol):
    """Produce one MEvaluation verdict for a candidate unit against a case.

    The single seam between the loop and the verdict producer. The 1.0 default
    (InProcessEmitter) runs evaluate() in-process; a 2.0 implementation runs it
    out-of-process and returns the same MEvaluation across the boundary. runtime_
    checkable so a consumer or test can assert an object satisfies the seam."""

    def emit(self, case_dir, candidate_dir, timeout: float = 30.0) -> MEvaluation: ...


class InProcessEmitter:
    """The 1.0 default emitter: emit() delegates to mevaluator.evaluate in THIS
    process and returns its MEvaluation unchanged. It wraps evaluate(); it does not
    reimplement any gate, scoring, or equivalence logic, so the verdict logic lives
    in exactly one place (mevaluator.evaluate).

    The evaluate delegate defaults to the production mevaluator.evaluate. It is a
    constructor argument only so the in-process orchestration stays testable without
    Docker (the pre-existing loop test seam), NOT as a second implementation: every
    instance is still the in-process emitter calling whatever in-process evaluate it
    was handed."""

    def __init__(self, evaluate=evaluate):
        self._evaluate = evaluate

    def emit(self, case_dir, candidate_dir, timeout=30.0) -> MEvaluation:
        return self._evaluate(case_dir, candidate_dir, timeout)
