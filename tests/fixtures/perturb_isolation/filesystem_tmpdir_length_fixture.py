"""Isolation fixture for the Filesystem-state dimension (tmpdir path
length). NOT collected by the main suite.

LIMIT is a synthetic threshold chosen for this fixture, not a real OS path
limit — it exists so the harness's control over tmpdir length is provable
with a clean, deterministic oracle, independent of any platform-specific
MAX_PATH behavior.
"""

import tempfile

LIMIT = 190


def test_tmpdir_path_is_short():
    assert len(tempfile.gettempdir()) < LIMIT
