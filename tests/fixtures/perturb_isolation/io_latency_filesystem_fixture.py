"""Isolation fixture for the IO-latency dimension (filesystem target). NOT
collected by the main suite.

Opens this very file; under the default (unpatched) `open`, that completes
in well under a millisecond. Under injected open delay, it blows the
budget.
"""

import time

BUDGET_SECONDS = 0.2


def test_open_completes_within_budget():
    start = time.monotonic()
    handle = open(__file__)
    handle.close()
    elapsed = time.monotonic() - start
    assert elapsed < BUDGET_SECONDS
