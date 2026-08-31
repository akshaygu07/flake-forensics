from __future__ import annotations

import json
import subprocess
import sys
import textwrap


def test_cli_baseline_reports_flake_rate_and_unknown_cause(tmp_path):
    test_file = tmp_path / "test_always_pass.py"
    test_file.write_text(
        textwrap.dedent(
            """
            def test_it():
                assert True
            """
        )
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "flake_forensics.cli",
            "baseline",
            f"{test_file}::test_it",
            "--runs",
            "3",
        ],
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["runs"] == 3
    assert payload["passes"] == 3
    assert payload["flake_rate"] == 0.0
    assert payload["cause"] == "UNKNOWN"
