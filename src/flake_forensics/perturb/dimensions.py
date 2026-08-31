"""One function per perturbation dimension. Each stresses exactly one
suspected cause and reports the resulting flake rate the same shape as the
naive baseline (`BaselineResult`) — Phase 1 is about producing trustworthy,
isolated measurements per dimension, not about classification yet.
"""

from __future__ import annotations

import random as _random
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from ..baseline import BaselineResult
from ..cause import Cause
from .runner import run_node_ids_once

_TMPDIR_ENV_VARS = ("TMPDIR", "TEMP", "TMP")


def _aggregate(test_id: str, outcomes: list[str]) -> BaselineResult:
    passes = outcomes.count("pass")
    failures = outcomes.count("fail")
    errors = outcomes.count("error")
    runs = len(outcomes)
    return BaselineResult(
        test_id=test_id,
        runs=runs,
        passes=passes,
        failures=failures,
        errors=errors,
        flake_rate=(failures + errors) / runs,
        cause=Cause.UNKNOWN,
    )


def run_rng(test_id: str, mode: str = "vary", seed: int = 1234, runs: int = 20) -> BaselineResult:
    """Vary the global `random` seed (default CPython auto-seeding, i.e. do
    nothing extra) or freeze it to a fixed value before the test runs.
    """
    if mode not in ("vary", "freeze"):
        raise ValueError("mode must be 'vary' or 'freeze'")
    env = {"FF_RNG_MODE": mode}
    if mode == "freeze":
        env["FF_RNG_SEED"] = str(seed)
    outcomes = [run_node_ids_once([test_id], env_overrides=env) for _ in range(runs)]
    return _aggregate(test_id, outcomes)


def run_clock(test_id: str, instant: datetime, runs: int = 20) -> BaselineResult:
    """Freeze wall-clock time (`datetime.now`, `time.time`, ...) at `instant`
    for the whole test process, via freezegun. Use this to probe midnight,
    month, DST, and leap-day boundaries.
    """
    env = {"FF_CLOCK_INSTANT": instant.isoformat()}
    outcomes = [run_node_ids_once([test_id], env_overrides=env) for _ in range(runs)]
    return _aggregate(test_id, outcomes)


def run_concurrency(
    test_id: str,
    switch_interval: float | None = None,
    contention: str = "none",
    contention_workers: int = 4,
    runs: int = 20,
) -> BaselineResult:
    """Force frequent thread yields (`sys.setswitchinterval`) and/or add
    background thread or process pressure while the test runs.
    """
    if contention not in ("none", "thread", "process"):
        raise ValueError("contention must be 'none', 'thread', or 'process'")
    env = {"FF_CONTENTION": contention, "FF_CONTENTION_WORKERS": str(contention_workers)}
    if switch_interval is not None:
        env["FF_SWITCH_INTERVAL"] = str(switch_interval)
    outcomes = [run_node_ids_once([test_id], env_overrides=env) for _ in range(runs)]
    return _aggregate(test_id, outcomes)


def run_order_isolation(test_id: str, runs: int = 20) -> BaselineResult:
    """Run the target test completely alone, once per rep."""
    outcomes = [run_node_ids_once([test_id]) for _ in range(runs)]
    return _aggregate(test_id, outcomes)


def run_order_after(target_id: str, predecessor_id: str, runs: int = 20) -> BaselineResult:
    """Run `predecessor_id` immediately before `target_id` in the same
    session, once per rep, and report `target_id`'s outcome. Call this once
    per candidate predecessor to find which specific test pollutes state.
    """
    outcomes = [run_node_ids_once([predecessor_id, target_id]) for _ in range(runs)]
    return _aggregate(target_id, outcomes)


def run_order_shuffled(
    target_id: str,
    module_files: list[str],
    shuffles: int = 20,
    seed: int | None = None,
) -> BaselineResult:
    """Run a set of whole test modules (files) in a freshly shuffled order,
    once per shuffle, and report `target_id`'s outcome each time.
    `module_files` must include the file `target_id` lives in.
    """
    rng = _random.Random(seed)
    outcomes = []
    for _ in range(shuffles):
        files = list(module_files)
        rng.shuffle(files)
        outcomes.append(run_node_ids_once(files, target_node_id=target_id))
    return _aggregate(target_id, outcomes)


def run_timezone(test_id: str, instant: datetime, tz_offset_hours: float, runs: int = 20) -> BaselineResult:
    """Freeze time at `instant` like `run_clock`, but also shift what naive
    local time (`datetime.now()`) reads relative to UTC by `tz_offset_hours`
    (freezegun's `tz_offset`, applied in-process). This deliberately doesn't
    touch the real OS timezone — there's no portable, unprivileged way to do
    that, especially on Windows, where `time.tzset` doesn't exist and the C
    runtime doesn't honor `TZ` the way POSIX does (verified empirically).
    Use 0 for UTC, a fractional value for a half-hour-offset zone, and two
    calls at different instants with different offsets to model a
    DST-observing zone's transition.
    """
    env = {
        "FF_CLOCK_INSTANT": instant.isoformat(),
        "FF_TZ_OFFSET_HOURS": str(tz_offset_hours),
    }
    outcomes = [run_node_ids_once([test_id], env_overrides=env) for _ in range(runs)]
    return _aggregate(test_id, outcomes)


def run_io_latency(
    test_id: str,
    delay_seconds: float,
    targets: tuple[str, ...] = ("socket", "filesystem"),
    runs: int = 20,
) -> BaselineResult:
    """Inject a fixed delay before every `socket.socket.connect` and/or
    `open()` call, via monkeypatching inside the subprocess.
    """
    for t in targets:
        if t not in ("socket", "filesystem"):
            raise ValueError("targets must be 'socket' and/or 'filesystem'")
    env = {
        "FF_IO_DELAY_SECONDS": str(delay_seconds),
        "FF_IO_DELAY_TARGETS": ",".join(targets),
    }
    outcomes = [run_node_ids_once([test_id], env_overrides=env) for _ in range(runs)]
    return _aggregate(test_id, outcomes)


def run_resource_limits(
    test_id: str,
    nofile: int | None = None,
    address_space_bytes: int | None = None,
    runs: int = 20,
) -> BaselineResult:
    """Constrain the subprocess's open-file-descriptor count and/or address
    space via POSIX rlimit before the test runs.

    Not supported on Windows: `resource.setrlimit` doesn't exist there, and
    there's no faithful cross-platform substitute, so this raises
    immediately rather than silently doing nothing or faking a limit.
    """
    if sys.platform == "win32":
        raise NotImplementedError(
            "Resource-limits perturbation requires POSIX rlimit support "
            "(Linux/macOS); not available on Windows."
        )
    if nofile is None and address_space_bytes is None:
        raise ValueError("must set at least one of nofile or address_space_bytes")
    env = {}
    if nofile is not None:
        env["FF_RLIMIT_NOFILE"] = str(nofile)
    if address_space_bytes is not None:
        env["FF_RLIMIT_AS"] = str(address_space_bytes)
    outcomes = [run_node_ids_once([test_id], env_overrides=env) for _ in range(runs)]
    return _aggregate(test_id, outcomes)


def run_locale(test_id: str, locale_name: str, runs: int = 20) -> BaselineResult:
    """Set the process locale (`LC_ALL`) via `locale.setlocale` before the
    test runs. If `locale_name` isn't installed on this system, pytest's own
    configure step raises for every rep — that surfaces as an "error"
    outcome per run, not a silent false pass.
    """
    env = {"FF_LOCALE": locale_name}
    outcomes = [run_node_ids_once([test_id], env_overrides=env) for _ in range(runs)]
    return _aggregate(test_id, outcomes)


def run_filesystem_tmpdir_length(test_id: str, path_length: str = "short", runs: int = 20) -> BaselineResult:
    """Point the process's tempdir (`TMPDIR`/`TEMP`/`TMP`) at either a short
    path or a deliberately long one before each run.
    """
    if path_length not in ("short", "long"):
        raise ValueError("path_length must be 'short' or 'long'")
    outcomes = []
    for _ in range(runs):
        base = Path(tempfile.gettempdir())
        if path_length == "short":
            tmp_dir = base / "ff-s"
        else:
            target_total = 200
            padding = max(target_total - len(str(base)) - len("ff-long-") - 1, 20)
            tmp_dir = base / f"ff-long-{'x' * padding}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        env = {var: str(tmp_dir) for var in _TMPDIR_ENV_VARS}
        outcomes.append(run_node_ids_once([test_id], env_overrides=env))
    return _aggregate(test_id, outcomes)


def run_filesystem_prepolluted_tmpdir(test_id: str, polluted: bool, runs: int = 20) -> BaselineResult:
    """Point the process's tempdir at a fresh directory that either already
    contains a marker file left behind by a previous run, or is clean.
    """
    outcomes = []
    for _ in range(runs):
        tmp_dir = Path(tempfile.mkdtemp(prefix="ff-fs-"))
        if polluted:
            (tmp_dir / "pre_existing_marker.txt").write_text("polluted")
        env = {var: str(tmp_dir) for var in _TMPDIR_ENV_VARS}
        outcomes.append(run_node_ids_once([test_id], env_overrides=env))
    return _aggregate(test_id, outcomes)
