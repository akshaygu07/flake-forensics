"""Isolation fixture for the Timezone dimension. NOT collected by the main
suite.

Passes iff naive local time is exactly 4 hours behind UTC at the moment
this runs (as if the process were in an EDT-like zone). Under the default
(no timezone perturbation, local == UTC) or any other offset, this fails.
"""

from datetime import datetime


def test_local_is_four_hours_behind_utc():
    local = datetime.now()
    utc = datetime.utcnow()
    assert (utc - local).total_seconds() == 4 * 3600
