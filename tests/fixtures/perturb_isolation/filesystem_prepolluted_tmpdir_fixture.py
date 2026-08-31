"""Isolation fixture for the Filesystem-state dimension (pre-polluted
tmpdir). NOT collected by the main suite.
"""

import tempfile
from pathlib import Path


def test_tmpdir_has_no_leftover_marker():
    marker = Path(tempfile.gettempdir()) / "pre_existing_marker.txt"
    assert not marker.exists()
