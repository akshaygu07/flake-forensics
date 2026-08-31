# Flake Forensics

Tells you why a flaky pytest test is flaky, not just that it is.

Every CI vendor detects flakes by rerunning tests and looking at pass/fail
ratios. None of them tell you the cause. This tool runs a test under a
*perturbation matrix* — controlled, isolated environmental manipulations,
each stressing exactly one suspected cause (test order, clock, timezone,
RNG, concurrency, I/O latency, resource limits, filesystem state) — and
classifies the cause from the resulting fingerprint.

Target for v1: **Python + pytest only.** See `CONTEXT.md` for the phase plan
and current status; this project follows an explicit phase gate (Phase 0
through Phase 5) with each phase's exit criteria written out before work on
it starts.

## Status: Phase 1 (dimensions implemented; CI not yet verified)

Phase 0's naive baseline is done — the thing every CI vendor already does.
It reruns a test N times, identically, in isolated subprocesses, and
reports the flake rate. **It never reports a cause; `cause` is always
`UNKNOWN`.** It exists so every later phase has an honest number (accuracy,
wall-clock cost) to beat.

Phase 1 is the perturbation harness. All 8 dimensions are implemented —
RNG, Clock, Order, Concurrency, Timezone, IO latency, Resource limits,
Filesystem state (locale, tmpdir path length, pre-polluted tmpdir) — each
proven, in `tests/test_perturbation_isolation.py`, to trigger only its own
purpose-built fixture and not leak into any other dimension's fixture.
Resource limits is POSIX-only (no faithful Windows equivalent to `rlimit`;
`run_resource_limits` raises `NotImplementedError` on Windows rather than
faking it) and its tests are skipped on this dev machine, not yet run on
the Linux CI matrix. See `CONTEXT.md` for exact status and open risks.

## Install

```bash
pip install -e ".[dev]"
```

## Usage

Naive baseline — no cause, ever:

```bash
flake-forensics baseline tests/test_foo.py::test_bar --runs 50
```

```json
{
  "test_id": "tests/test_foo.py::test_bar",
  "runs": 50,
  "passes": 47,
  "failures": 3,
  "errors": 0,
  "flake_rate": 0.06,
  "cause": "UNKNOWN"
}
```

Perturbation dimensions (library only for now, no CLI subcommand yet):

```python
from datetime import datetime
from flake_forensics.perturb import (
    run_rng, run_clock, run_order_after, run_concurrency,
    run_timezone, run_io_latency, run_resource_limits,
    run_locale, run_filesystem_tmpdir_length, run_filesystem_prepolluted_tmpdir,
)

run_rng("tests/test_foo.py::test_bar", mode="freeze", seed=1234, runs=50)
run_clock("tests/test_foo.py::test_bar", instant=datetime(2026, 1, 1), runs=50)
run_order_after("tests/test_foo.py::test_bar", "tests/test_other.py::test_setup", runs=50)
run_concurrency("tests/test_foo.py::test_bar", switch_interval=1e-6, contention="thread", runs=50)
run_timezone("tests/test_foo.py::test_bar", instant=datetime(2026, 1, 1), tz_offset_hours=-4, runs=50)
run_io_latency("tests/test_foo.py::test_bar", delay_seconds=0.3, targets=("socket", "filesystem"), runs=50)
run_resource_limits("tests/test_foo.py::test_bar", nofile=64, runs=50)  # POSIX only
run_locale("tests/test_foo.py::test_bar", locale_name="de_DE.UTF-8", runs=50)
run_filesystem_tmpdir_length("tests/test_foo.py::test_bar", path_length="long", runs=50)
run_filesystem_prepolluted_tmpdir("tests/test_foo.py::test_bar", polluted=True, runs=50)
```

Each returns the same `BaselineResult` shape as the baseline (`cause` is
still always `UNKNOWN` — Phase 1 is about trustworthy per-dimension
measurement, not classification; that's Phase 2).

## Development

```bash
pip install -e ".[dev]"
pytest -v
```

## Non-goals (v1)

No web UI, no CI integration, no second language, no LLM in the
classification loop. See `CONTEXT.md`.
