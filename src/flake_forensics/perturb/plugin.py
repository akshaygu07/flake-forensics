"""A pytest plugin that applies exactly one perturbation dimension's effect
inside the subprocess it's loaded into.

This is never registered globally (no entry point). The runner loads it
explicitly per subprocess via `-p flake_forensics.perturb.plugin` and
configures it entirely through environment variables, so a plain,
unperturbed pytest run of this repo's own test suite never touches it.

Each dimension is applied independently based on which env vars are present,
which is exactly what the isolation tests in `tests/test_perturbation_isolation.py`
exist to verify: turning on dimension A must not change the observed
behavior of a test that is only sensitive to dimension B.
"""

from __future__ import annotations

import builtins
import locale
import os
import random
import socket
import sys
import threading
import time
from multiprocessing import Process

_contention_threads: list[threading.Thread] = []
_contention_stop = threading.Event()
_contention_processes: list[Process] = []
_freezer = None
_orig_open = None
_orig_connect = None
_orig_locale = None


def _thread_spin() -> None:
    while not _contention_stop.is_set():
        pass


def _process_spin() -> None:
    while True:
        pass


def pytest_configure(config) -> None:
    global _freezer, _orig_open, _orig_connect, _orig_locale

    rng_mode = os.environ.get("FF_RNG_MODE")
    if rng_mode == "freeze":
        random.seed(int(os.environ["FF_RNG_SEED"]))
    # rng_mode == "vary" (or unset): leave CPython's own auto-seeding
    # (os.urandom at interpreter startup) in place. That already IS a
    # varying seed; there's nothing extra to do.

    instant = os.environ.get("FF_CLOCK_INSTANT")
    if instant:
        import freezegun

        tz_offset = float(os.environ.get("FF_TZ_OFFSET_HOURS", "0"))
        _freezer = freezegun.freeze_time(instant, tz_offset=tz_offset)
        _freezer.start()

    io_delay = os.environ.get("FF_IO_DELAY_SECONDS")
    if io_delay:
        delay = float(io_delay)
        targets = os.environ.get("FF_IO_DELAY_TARGETS", "socket,filesystem").split(",")

        if "filesystem" in targets:
            _orig_open = builtins.open

            def _delayed_open(*args, **kwargs):
                time.sleep(delay)
                return _orig_open(*args, **kwargs)

            builtins.open = _delayed_open

        if "socket" in targets:
            _orig_connect = socket.socket.connect

            def _delayed_connect(self, *args, **kwargs):
                time.sleep(delay)
                return _orig_connect(self, *args, **kwargs)

            socket.socket.connect = _delayed_connect

    locale_name = os.environ.get("FF_LOCALE")
    if locale_name:
        _orig_locale = locale.setlocale(locale.LC_ALL)
        locale.setlocale(locale.LC_ALL, locale_name)

    if os.environ.get("FF_RLIMIT_NOFILE") or os.environ.get("FF_RLIMIT_AS"):
        if sys.platform == "win32":
            raise RuntimeError(
                "Resource-limits perturbation requires POSIX rlimit support; "
                "not available on Windows."
            )
        import resource

        nofile = os.environ.get("FF_RLIMIT_NOFILE")
        if nofile:
            _, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            resource.setrlimit(resource.RLIMIT_NOFILE, (int(nofile), hard))

        as_limit = os.environ.get("FF_RLIMIT_AS")
        if as_limit:
            _, hard = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(resource.RLIMIT_AS, (int(as_limit), hard))

    switch_interval = os.environ.get("FF_SWITCH_INTERVAL")
    if switch_interval:
        sys.setswitchinterval(float(switch_interval))

    contention = os.environ.get("FF_CONTENTION", "none")
    workers = int(os.environ.get("FF_CONTENTION_WORKERS", "4"))
    if contention == "thread":
        for _ in range(workers):
            t = threading.Thread(target=_thread_spin, daemon=True)
            t.start()
            _contention_threads.append(t)
    elif contention == "process":
        for _ in range(workers):
            p = Process(target=_process_spin, daemon=True)
            p.start()
            _contention_processes.append(p)


def pytest_unconfigure(config) -> None:
    global _freezer, _orig_open, _orig_connect, _orig_locale

    _contention_stop.set()
    for t in _contention_threads:
        t.join(timeout=2)
    _contention_threads.clear()

    for p in _contention_processes:
        p.terminate()
        p.join(timeout=2)
    _contention_processes.clear()

    if _freezer is not None:
        _freezer.stop()
        _freezer = None

    if _orig_open is not None:
        builtins.open = _orig_open
        _orig_open = None

    if _orig_connect is not None:
        socket.socket.connect = _orig_connect
        _orig_connect = None

    if _orig_locale is not None:
        locale.setlocale(locale.LC_ALL, _orig_locale)
        _orig_locale = None
    # Resource limits are deliberately not restored: the process is about
    # to exit, and rlimit's soft limit can only be lowered without
    # elevated privileges, so raising it back may fail anyway.
