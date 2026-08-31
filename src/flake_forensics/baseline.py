"""The naive baseline: what every CI vendor already does.

Rerun a test N times, identically, in isolated subprocesses, and report the
observed flake rate. This tells you THAT a test is flaky. It never tells you
WHY, so `cause` is always UNKNOWN. Every later phase's accuracy and cost is
measured against this.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from .cause import Cause

Outcome = str  # one of "pass", "fail", "error"


@dataclass(frozen=True)
class BaselineResult:
    test_id: str
    runs: int
    passes: int
    failures: int
    errors: int
    flake_rate: float
    cause: Cause = Cause.UNKNOWN

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "runs": self.runs,
            "passes": self.passes,
            "failures": self.failures,
            "errors": self.errors,
            "flake_rate": self.flake_rate,
            "cause": self.cause.value,
        }


def _run_once(test_id: str, pytest_args: list[str] | None = None) -> Outcome:
    """Run a single pytest node id in a fresh subprocess.

    A fresh process per run is deliberate: it avoids leaking state (import
    caches, monkeypatches, global RNG state) between reruns, which would
    itself be an uncontrolled perturbation.
    """
    cmd = [sys.executable, "-m", "pytest", test_id, "-q", "--no-header", "-p", "no:cacheprovider"]
    if pytest_args:
        cmd.extend(pytest_args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return "pass"
    if proc.returncode == 1:
        return "fail"
    return "error"  # collection error, internal pytest error, etc.


def run_baseline(
    test_id: str,
    runs: int = 50,
    pytest_args: list[str] | None = None,
) -> BaselineResult:
    """Rerun `test_id` `runs` times and report the flake rate. No cause.

    Args:
        test_id: a pytest node id, e.g. "tests/test_foo.py::test_bar".
        runs: number of identical reruns.
        pytest_args: extra args forwarded to each pytest invocation.
    """
    if runs < 1:
        raise ValueError("runs must be >= 1")

    outcomes = [_run_once(test_id, pytest_args) for _ in range(runs)]
    passes = outcomes.count("pass")
    failures = outcomes.count("fail")
    errors = outcomes.count("error")

    return BaselineResult(
        test_id=test_id,
        runs=runs,
        passes=passes,
        failures=failures,
        errors=errors,
        flake_rate=(failures + errors) / runs,
        cause=Cause.UNKNOWN,
    )
