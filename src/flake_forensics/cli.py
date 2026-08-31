from __future__ import annotations

import argparse
import json
import sys

from .baseline import run_baseline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flake-forensics")
    sub = parser.add_subparsers(dest="command", required=True)

    baseline_p = sub.add_parser(
        "baseline",
        help="Naive baseline: rerun a test N times identically, report flake rate. No cause.",
    )
    baseline_p.add_argument("test_id", help="pytest node id, e.g. tests/test_foo.py::test_bar")
    baseline_p.add_argument("--runs", type=int, default=50, help="number of reruns (default: 50)")

    args = parser.parse_args(argv)

    if args.command == "baseline":
        result = run_baseline(args.test_id, runs=args.runs)
        json.dump(result.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
