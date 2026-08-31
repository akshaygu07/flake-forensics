"""Isolation fixture for the Concurrency dimension. NOT collected by the
main suite.

A check-then-act race on a shared dict, with a function call between the
read and the write. That call boundary matters: CPython's eval-breaker is
only checked at loop backedges and call sites, not at arbitrary points
inside a straight-line loop body, so a bare `c = d['k']; d['k'] = c + 1`
with no call in between turns out to be effectively atomic on this
interpreter regardless of switch interval (verified empirically — up to
5,000,000 iterations x 8 threads never raced). Real check-then-act bugs
almost always have a call (or I/O) in the gap, so this fixture models that
faithfully instead of a shape CPython happens to make atomic.

Calibrated so that under the default switch interval (5ms) with no
contention this reliably passes, and under a very short switch interval
plus background thread pressure it reliably fails (see
tests/test_perturbation_isolation.py).

ITERATIONS/THREAD_COUNT were first tuned only on Windows 11 / CPython 3.14
(1500 x 4) and turned out to race far less reliably on Linux CI
(ubuntu-latest, CPython 3.10-3.12: 3/5 reps instead of 5/5) — recalibrated
higher across the board specifically so the race is reliable on both
platforms, not just the one it was written on.
"""

import threading

ITERATIONS = 20000
THREAD_COUNT = 8


def _yield_point() -> None:
    """A no-op function call — just something for CPython to check the
    eval-breaker at, between the read and the write below."""


def test_race_on_shared_counter():
    shared = {"count": 0}

    def increment() -> None:
        for _ in range(ITERATIONS):
            current = shared["count"]
            _yield_point()
            shared["count"] = current + 1

    threads = [threading.Thread(target=increment) for _ in range(THREAD_COUNT)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert shared["count"] == THREAD_COUNT * ITERATIONS
