"""Isolation fixture for the Clock dimension. NOT collected by the main
suite.

Passes iff wall-clock time was frozen at exactly TARGET. Under the real
system clock (any date other than TARGET, i.e. always, in practice) this
fails.
"""

from datetime import datetime

TARGET = "2026-01-01T00:00:00"  # a midnight boundary


def test_frozen_at_target_instant():
    assert datetime.now().isoformat(timespec="seconds") == TARGET
