"""Phase 1 exit criterion: each perturbation dimension must be verified with
a purpose-built fixture that ONLY fails under that perturbation, not under
any other. Every test below either proves a dimension triggers its own
fixture, or proves a dimension does NOT leak into another dimension's
fixture.

These spawn real subprocesses (one pytest invocation per rep), so this file
is slower than the rest of the suite by design — the whole point is
observing actual subprocess behavior, not something a mock could stand in
for.
"""

from __future__ import annotations

import locale as _locale
import sys
from datetime import datetime
from pathlib import Path

import pytest

from flake_forensics.perturb.dimensions import (
    run_clock,
    run_concurrency,
    run_filesystem_prepolluted_tmpdir,
    run_filesystem_tmpdir_length,
    run_io_latency,
    run_locale,
    run_order_after,
    run_order_isolation,
    run_order_shuffled,
    run_resource_limits,
    run_rng,
    run_timezone,
)
from flake_forensics.perturb.runner import run_node_ids_once

FIXTURES = Path(__file__).parent / "fixtures" / "perturb_isolation"

RNG_TEST = f"{FIXTURES / 'rng_fixture.py'}::test_seed_1234_first_draw"
CLOCK_TEST = f"{FIXTURES / 'clock_fixture.py'}::test_frozen_at_target_instant"
CONCURRENCY_TEST = f"{FIXTURES / 'concurrency_fixture.py'}::test_race_on_shared_counter"
TIMEZONE_TEST = f"{FIXTURES / 'timezone_fixture.py'}::test_local_is_four_hours_behind_utc"
IO_SOCKET_TEST = f"{FIXTURES / 'io_latency_socket_fixture.py'}::test_local_connect_completes_within_budget"
IO_FS_TEST = f"{FIXTURES / 'io_latency_filesystem_fixture.py'}::test_open_completes_within_budget"
TMPDIR_LENGTH_TEST = f"{FIXTURES / 'filesystem_tmpdir_length_fixture.py'}::test_tmpdir_path_is_short"
PREPOLLUTED_TEST = f"{FIXTURES / 'filesystem_prepolluted_tmpdir_fixture.py'}::test_tmpdir_has_no_leftover_marker"
LOCALE_TEST = f"{FIXTURES / 'locale_fixture.py'}::test_decimal_separator_is_dot"
RESOURCE_LIMITS_TEST = f"{FIXTURES / 'resource_limits_fixture.py'}::test_open_many_files_within_limit"
ORDER_FILE = str(FIXTURES / "order_fixture.py")
ORDER_A = f"{ORDER_FILE}::test_a_pollutes"
ORDER_B = f"{ORDER_FILE}::test_b_depends_on_pollution"
ORDER_NEUTRAL_FILE = str(FIXTURES / "order_fixture_b.py")

RNG_SEED = 1234
CLOCK_TARGET = datetime.fromisoformat("2026-01-01T00:00:00")
REPS = 5

CONCURRENCY_KWARGS = dict(switch_interval=1e-6, contention="thread", contention_workers=8)

TEST_LOCALE_NAME = "de_DE.UTF-8"


def _locale_available(name: str) -> bool:
    current = _locale.setlocale(_locale.LC_ALL)
    try:
        _locale.setlocale(_locale.LC_ALL, name)
        return True
    except _locale.Error:
        return False
    finally:
        _locale.setlocale(_locale.LC_ALL, current)


LOCALE_AVAILABLE = _locale_available(TEST_LOCALE_NAME)


# ---------------------------------------------------------------------------
# Each dimension triggers its own fixture.
# ---------------------------------------------------------------------------


def test_rng_freeze_triggers_rng_fixture():
    result = run_rng(RNG_TEST, mode="freeze", seed=RNG_SEED, runs=REPS)
    assert result.passes == REPS


def test_rng_vary_does_not_trigger_rng_fixture():
    result = run_rng(RNG_TEST, mode="vary", runs=REPS)
    assert result.failures == REPS


def test_clock_freeze_triggers_clock_fixture():
    result = run_clock(CLOCK_TEST, instant=CLOCK_TARGET, runs=REPS)
    assert result.passes == REPS


def test_clock_at_other_instant_does_not_trigger_clock_fixture():
    other = datetime.fromisoformat("2026-06-15T12:30:00")
    result = run_clock(CLOCK_TEST, instant=other, runs=REPS)
    assert result.failures == REPS


def test_order_isolation_fails():
    result = run_order_isolation(ORDER_B, runs=REPS)
    assert result.failures == REPS


def test_order_after_predecessor_passes():
    result = run_order_after(ORDER_B, ORDER_A, runs=REPS)
    assert result.passes == REPS


def test_order_shuffled_module_order_does_not_break_within_module_order():
    # order_fixture.py always collects test_a before test_b (pytest keeps
    # in-file definition order), regardless of which FILE runs first among
    # the shuffled set — so shuffling which module goes first must not
    # affect this target's outcome.
    result = run_order_shuffled(
        ORDER_B,
        module_files=[ORDER_FILE, ORDER_NEUTRAL_FILE],
        shuffles=REPS,
        seed=42,
    )
    assert result.passes == REPS


def test_concurrency_baseline_does_not_race():
    result = run_concurrency(CONCURRENCY_TEST, runs=REPS)
    assert result.failures == 0


def test_concurrency_low_switch_interval_with_contention_races():
    result = run_concurrency(CONCURRENCY_TEST, runs=REPS, **CONCURRENCY_KWARGS)
    assert result.failures == REPS


# ---------------------------------------------------------------------------
# Cross-dimension isolation: dimension A must not leak into dimension B's
# fixture. This is the actual Phase 1 exit criterion ("if your clock offset
# perturbation also happens to change RNG behavior, the dimensions are
# entangled").
# ---------------------------------------------------------------------------


def test_clock_does_not_leak_into_rng_fixture():
    result = run_clock(RNG_TEST, instant=CLOCK_TARGET, runs=REPS)
    assert result.failures == REPS


def test_rng_does_not_leak_into_clock_fixture():
    result = run_rng(CLOCK_TEST, mode="freeze", seed=RNG_SEED, runs=REPS)
    assert result.failures == REPS


def test_concurrency_does_not_leak_into_rng_fixture():
    result = run_concurrency(RNG_TEST, runs=REPS, **CONCURRENCY_KWARGS)
    assert result.failures == REPS


def test_concurrency_does_not_leak_into_clock_fixture():
    result = run_concurrency(CLOCK_TEST, runs=REPS, **CONCURRENCY_KWARGS)
    assert result.failures == REPS


def test_rng_freeze_does_not_leak_into_order_isolation_fixture():
    # Apply RNG-freeze env directly to the order fixture, alone (isolation
    # mode). Freezing the RNG must not somehow populate the module-level
    # pollution state that only test_a_pollutes sets.
    outcomes = [
        run_node_ids_once([ORDER_B], env_overrides={"FF_RNG_MODE": "freeze", "FF_RNG_SEED": str(RNG_SEED)})
        for _ in range(REPS)
    ]
    assert all(o == "fail" for o in outcomes)


def test_clock_freeze_does_not_leak_into_order_isolation_fixture():
    outcomes = [
        run_node_ids_once([ORDER_B], env_overrides={"FF_CLOCK_INSTANT": CLOCK_TARGET.isoformat()})
        for _ in range(REPS)
    ]
    assert all(o == "fail" for o in outcomes)


def test_order_after_does_not_leak_into_rng_fixture():
    # Running RNG_TEST preceded by an unrelated passing predecessor (order
    # perturbation's mechanism) must not accidentally make it pass.
    result = run_order_after(RNG_TEST, ORDER_A, runs=REPS)
    assert result.failures == REPS


# ---------------------------------------------------------------------------
# Timezone
# ---------------------------------------------------------------------------


def test_timezone_offset_triggers_timezone_fixture():
    result = run_timezone(TIMEZONE_TEST, instant=CLOCK_TARGET, tz_offset_hours=-4, runs=REPS)
    assert result.passes == REPS


def test_timezone_utc_does_not_trigger_timezone_fixture():
    result = run_timezone(TIMEZONE_TEST, instant=CLOCK_TARGET, tz_offset_hours=0, runs=REPS)
    assert result.failures == REPS


def test_timezone_does_not_leak_into_rng_fixture():
    result = run_timezone(RNG_TEST, instant=CLOCK_TARGET, tz_offset_hours=-4, runs=REPS)
    assert result.failures == REPS


def test_rng_does_not_leak_into_timezone_fixture():
    result = run_rng(TIMEZONE_TEST, mode="freeze", seed=RNG_SEED, runs=REPS)
    assert result.failures == REPS


# ---------------------------------------------------------------------------
# IO latency
# ---------------------------------------------------------------------------


def test_io_latency_socket_target_triggers_io_socket_fixture():
    result = run_io_latency(IO_SOCKET_TEST, delay_seconds=0.3, targets=("socket",), runs=REPS)
    assert result.failures == REPS


def test_io_latency_filesystem_target_does_not_trigger_io_socket_fixture():
    result = run_io_latency(IO_SOCKET_TEST, delay_seconds=0.3, targets=("filesystem",), runs=REPS)
    assert result.passes == REPS


def test_io_latency_filesystem_target_triggers_io_filesystem_fixture():
    result = run_io_latency(IO_FS_TEST, delay_seconds=0.3, targets=("filesystem",), runs=REPS)
    assert result.failures == REPS


def test_io_latency_socket_target_does_not_trigger_io_filesystem_fixture():
    result = run_io_latency(IO_FS_TEST, delay_seconds=0.3, targets=("socket",), runs=REPS)
    assert result.passes == REPS


def test_io_latency_does_not_leak_into_rng_fixture():
    result = run_io_latency(RNG_TEST, delay_seconds=0.3, runs=REPS)
    assert result.failures == REPS


def test_rng_does_not_leak_into_io_socket_fixture():
    result = run_rng(IO_SOCKET_TEST, mode="freeze", seed=RNG_SEED, runs=REPS)
    assert result.passes == REPS


def test_rng_does_not_leak_into_io_filesystem_fixture():
    result = run_rng(IO_FS_TEST, mode="freeze", seed=RNG_SEED, runs=REPS)
    assert result.passes == REPS


# ---------------------------------------------------------------------------
# Resource limits (POSIX only — see run_resource_limits' docstring)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="resource.setrlimit is POSIX-only")
def test_resource_limits_low_nofile_triggers_resource_limits_fixture():
    result = run_resource_limits(RESOURCE_LIMITS_TEST, nofile=10, runs=REPS)
    assert result.passes == 0
    assert result.failures + result.errors == REPS


@pytest.mark.skipif(sys.platform == "win32", reason="resource.setrlimit is POSIX-only")
def test_resource_limits_generous_nofile_does_not_trigger_resource_limits_fixture():
    result = run_resource_limits(RESOURCE_LIMITS_TEST, nofile=1024, runs=REPS)
    assert result.passes == REPS


@pytest.mark.skipif(sys.platform == "win32", reason="resource.setrlimit is POSIX-only")
def test_resource_limits_does_not_leak_into_rng_fixture():
    result = run_resource_limits(RNG_TEST, nofile=1024, runs=REPS)
    assert result.failures == REPS


@pytest.mark.skipif(sys.platform != "win32", reason="verifies the honest unsupported-platform path on Windows")
def test_resource_limits_raises_on_windows():
    with pytest.raises(NotImplementedError):
        run_resource_limits(RESOURCE_LIMITS_TEST, nofile=10, runs=1)


# ---------------------------------------------------------------------------
# Filesystem state: locale
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not LOCALE_AVAILABLE, reason=f"locale {TEST_LOCALE_NAME!r} not installed on this system")
def test_locale_triggers_locale_fixture():
    result = run_locale(LOCALE_TEST, locale_name=TEST_LOCALE_NAME, runs=REPS)
    assert result.failures == REPS


def test_locale_c_does_not_trigger_locale_fixture():
    result = run_locale(LOCALE_TEST, locale_name="C", runs=REPS)
    assert result.passes == REPS


@pytest.mark.skipif(not LOCALE_AVAILABLE, reason=f"locale {TEST_LOCALE_NAME!r} not installed on this system")
def test_locale_does_not_leak_into_rng_fixture():
    result = run_locale(RNG_TEST, locale_name=TEST_LOCALE_NAME, runs=REPS)
    assert result.failures == REPS


def test_rng_does_not_leak_into_locale_fixture():
    result = run_rng(LOCALE_TEST, mode="freeze", seed=RNG_SEED, runs=REPS)
    assert result.passes == REPS


# ---------------------------------------------------------------------------
# Filesystem state: tmpdir path length
# ---------------------------------------------------------------------------


def test_filesystem_long_tmpdir_triggers_tmpdir_length_fixture():
    result = run_filesystem_tmpdir_length(TMPDIR_LENGTH_TEST, path_length="long", runs=REPS)
    assert result.failures == REPS


def test_filesystem_short_tmpdir_does_not_trigger_tmpdir_length_fixture():
    result = run_filesystem_tmpdir_length(TMPDIR_LENGTH_TEST, path_length="short", runs=REPS)
    assert result.passes == REPS


def test_filesystem_tmpdir_length_does_not_leak_into_rng_fixture():
    result = run_filesystem_tmpdir_length(RNG_TEST, path_length="long", runs=REPS)
    assert result.failures == REPS


def test_rng_does_not_leak_into_tmpdir_length_fixture():
    result = run_rng(TMPDIR_LENGTH_TEST, mode="freeze", seed=RNG_SEED, runs=REPS)
    assert result.passes == REPS


# ---------------------------------------------------------------------------
# Filesystem state: pre-polluted tmpdir
# ---------------------------------------------------------------------------


def test_filesystem_prepolluted_triggers_prepolluted_fixture():
    result = run_filesystem_prepolluted_tmpdir(PREPOLLUTED_TEST, polluted=True, runs=REPS)
    assert result.failures == REPS


def test_filesystem_clean_tmpdir_does_not_trigger_prepolluted_fixture():
    result = run_filesystem_prepolluted_tmpdir(PREPOLLUTED_TEST, polluted=False, runs=REPS)
    assert result.passes == REPS


def test_filesystem_prepolluted_does_not_leak_into_rng_fixture():
    result = run_filesystem_prepolluted_tmpdir(RNG_TEST, polluted=True, runs=REPS)
    assert result.failures == REPS


def test_rng_does_not_leak_into_prepolluted_fixture():
    result = run_rng(PREPOLLUTED_TEST, mode="freeze", seed=RNG_SEED, runs=REPS)
    assert result.passes == REPS
