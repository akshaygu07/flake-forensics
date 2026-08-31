from __future__ import annotations

import textwrap

import pytest

from flake_forensics.baseline import run_baseline
from flake_forensics.cause import Cause


def _write(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(textwrap.dedent(body))
    return path


def test_deterministic_pass_has_zero_flake_rate(tmp_path):
    path = _write(
        tmp_path,
        "test_always_pass.py",
        """
        def test_it():
            assert True
        """,
    )
    result = run_baseline(f"{path}::test_it", runs=5)
    assert result.runs == 5
    assert result.passes == 5
    assert result.failures == 0
    assert result.flake_rate == 0.0
    assert result.cause is Cause.UNKNOWN


def test_deterministic_fail_has_full_flake_rate(tmp_path):
    path = _write(
        tmp_path,
        "test_always_fail.py",
        """
        def test_it():
            assert False
        """,
    )
    result = run_baseline(f"{path}::test_it", runs=5)
    assert result.runs == 5
    assert result.failures == 5
    assert result.flake_rate == 1.0
    assert result.cause is Cause.UNKNOWN


def test_baseline_never_assigns_a_cause_other_than_unknown(tmp_path):
    """Phase 0 exit criterion: the naive baseline reports flake rate with no
    cause. It must always report UNKNOWN, regardless of the observed flake
    rate, since it has no evidence to justify anything more specific.
    """
    path = _write(
        tmp_path,
        "test_flip.py",
        """
        import random

        def test_it():
            assert random.random() < 0.5
        """,
    )
    result = run_baseline(f"{path}::test_it", runs=8)
    assert result.cause is Cause.UNKNOWN


def test_invalid_runs_raises():
    with pytest.raises(ValueError):
        run_baseline("tests/test_baseline.py::test_it", runs=0)
