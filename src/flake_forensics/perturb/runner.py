"""Low-level subprocess runner shared by every perturbation dimension.

A single test's outcome can't be read off the pytest exit code once more
than one node id is involved (order perturbations deliberately run a
"pollution" test alongside the target), so every run goes through a
`--junitxml` report and the target's outcome is read from that instead.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

Outcome = str  # "pass" | "fail" | "error"

_PLUGIN = "flake_forensics.perturb.plugin"


def _target_outcome_from_junit(junit_path: Path, target_node_id: str) -> Outcome:
    target_name = target_node_id.split("::")[-1]
    tree = ET.parse(junit_path)
    for testcase in tree.iter("testcase"):
        if testcase.get("name") != target_name:
            continue
        if testcase.find("failure") is not None:
            return "fail"
        if testcase.find("error") is not None:
            return "error"
        if testcase.find("skipped") is not None:
            return "error"
        return "pass"
    return "error"  # target was never collected/run


def run_node_ids_once(
    node_ids: list[str],
    target_node_id: str | None = None,
    env_overrides: dict[str, str] | None = None,
    pytest_args: list[str] | None = None,
) -> Outcome:
    """Run `node_ids`, in the given order, in one fresh subprocess.

    Returns the outcome of `target_node_id` (default: the last node id) as
    read from a junit report, not the process exit code — the exit code
    reflects the whole session, which is meaningless when earlier node ids
    are deliberately there to set up state for the target rather than to
    pass or fail on their own.
    """
    if not node_ids:
        raise ValueError("node_ids must not be empty")
    target = target_node_id or node_ids[-1]

    with tempfile.TemporaryDirectory() as tmp:
        junit_path = Path(tmp) / "result.xml"
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            *node_ids,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:randomly",  # don't let an installed order-randomizer plugin override our explicit order
            "-p",
            _PLUGIN,
            f"--junitxml={junit_path}",
        ]
        if pytest_args:
            cmd.extend(pytest_args)

        env = dict(os.environ)
        if env_overrides:
            env.update(env_overrides)

        subprocess.run(cmd, capture_output=True, text=True, env=env)

        if not junit_path.exists():
            return "error"
        return _target_outcome_from_junit(junit_path, target)
