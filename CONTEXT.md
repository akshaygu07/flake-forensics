# Context and ground rules

Working notes on project state, kept honest per the CLAUDE.md mandate. Update
this file, don't just carry state in commit messages.

## Held-out corpus discipline

30% of the synthetic corpus and 30% of the mined corpus must be held out and
never inspected before Phase 4. **If that rule is ever broken, it must be
recorded right here, with what was seen and when, and the split must be
rebuilt.**

Status: no corpora exist yet (Phase 0). Nothing has been held out because
nothing has been built. This section will be updated the moment a split
exists.

## Phase status

- **Phase 0 — Skeleton and honest baseline: in progress.**
  - [x] Repo scaffolded (`src/flake_forensics`, `tests/`, CI).
  - [x] Naive baseline implemented: reruns a test N times identically in
        isolated subprocesses, reports flake rate, always emits
        `cause = UNKNOWN`.
  - [x] Baseline cause-classification accuracy is 0% by construction — it
        never claims a cause other than UNKNOWN, so it is only "correct"
        when a test's true label happens to be UNKNOWN (i.e. not flaky, or
        flaky for an unmodeled reason). Every later phase's accuracy and
        wall-clock cost is compared against this number and against this
        baseline's runtime.
  - [ ] CI verified green on a pushed branch (needs a remote — not yet
        pushed anywhere).
- **Phase 1 — Perturbation harness: 8 of 8 dimensions implemented.**
  - [x] RNG (`run_rng`, modes `vary`/`freeze`), Clock (`run_clock`, via
        freezegun), Order (`run_order_isolation` / `run_order_after` /
        `run_order_shuffled`), Concurrency (`run_concurrency`, via
        `sys.setswitchinterval` + thread/process contention) — all four
        implemented in `src/flake_forensics/perturb/`.
  - [x] Timezone (`run_timezone`, via freezegun's `tz_offset` — deliberately
        does **not** use `time.tzset`, see decision below), IO latency
        (`run_io_latency`, monkeypatches `socket.socket.connect` and/or
        `builtins.open` with a fixed delay, targets independently
        selectable), Resource limits (`run_resource_limits`, POSIX
        `resource.setrlimit` on `RLIMIT_NOFILE`/`RLIMIT_AS`; raises
        `NotImplementedError` immediately on Windows, see decision below),
        Filesystem state (three independent sub-perturbations: locale via
        `run_locale`, tmpdir path length via `run_filesystem_tmpdir_length`,
        pre-polluted tmpdir via `run_filesystem_prepolluted_tmpdir`) — all
        now implemented in `src/flake_forensics/perturb/`.
  - [x] Isolation proven for all eight (11 fixtures total, since IO latency
        and filesystem state each have multiple independently-triggerable
        fixtures): `tests/test_perturbation_isolation.py` (43 tests, 3
        skipped on Windows for the POSIX-only resource-limits behavior)
        shows each dimension triggers its own purpose-built fixture
        (`tests/fixtures/perturb_isolation/`) and does **not** change the
        outcome of another dimension's fixture (checked against the RNG
        fixture as the canary in both directions for every new dimension,
        matching the existing pattern). All non-skipped tests pass on this
        Windows 11 / CPython 3.14 machine.
  - [ ] Not yet verified: the 3 resource-limits tests that are skipped here
        (POSIX-only) still need to actually run green on the ubuntu-latest
        CI matrix once pushed — written against the documented behavior but
        never executed on Linux.
  - **Open risk, not yet checked:** the Concurrency fixture's calibration
    (1500 iterations x 4 threads, switch interval 1e-6) was tuned
    empirically on this Windows 11 / CPython 3.14 machine. GIL/scheduler
    timing is platform-sensitive; this has **not** been verified on the
    ubuntu-latest CI matrix (no remote pushed yet). If it turns out
    baseline races spuriously or perturbed doesn't race reliably on Linux,
    recalibrate rather than widen the assertion to paper over it.
  - **Resolved:** the Windows-portability question flagged here previously
    (`resource.setrlimit` and `time.tzset` are POSIX-only) is now decided,
    not just noted. Timezone sidesteps it entirely — freezegun's `tz_offset`
    patches `datetime.now()`/`utcnow()` in-process, so no real `TZ`/`tzset`
    change is needed on any platform. Resource limits has no such escape
    hatch (there's no faithful cross-platform substitute for rlimit), so it
    takes the honest-unsupported path: `run_resource_limits` raises
    `NotImplementedError` immediately on `sys.platform == "win32"` rather
    than silently no-op'ing or faking a limit.
- **Phase 2 — Fingerprinting and classification: not started.**
- **Phase 3 — Actionable output: not started.**
- **Phase 4 — Held-out evaluation: not started.**
- **Phase 5 — Second framework: not started; blocked on Phase 4 sign-off.**

## Corpus progress

- Synthetic corpus: 0 / 60 minimum written (need >= 6 per cause class, flake
  rates spanning ~2%-90%, some dual-cause, some deterministic negative
  controls). One example fixture exists at
  `tests/fixtures/corpus/unseeded_randomness_01.py` to establish the labeling
  convention (docstring header: `label`, `approx_flake_rate`, `notes`) — it
  does not count toward the 60.
- Mined corpus: 0 / 40 minimum recovered from real flaky-test-fix commits.

## Decisions made without asking

- Language/deps: stdlib + pytest only for the baseline; no extra
  dependencies added preemptively (perturbation harness will need more —
  add them when a specific dimension needs them, not before).
- Isolation strategy: each baseline rerun spawns a fresh `python -m pytest`
  subprocess rather than reusing one process, specifically so the baseline
  itself doesn't leak state between runs and contaminate the flake-rate
  measurement it's supposed to be establishing honestly.
- Packaging: hatchling + `src/` layout, `flake-forensics` console script.
- Not yet pushed to a git remote or committed — local repo only, awaiting
  review.
- Added `freezegun` as a real dependency (not dev-only) for the Clock
  dimension: it patches `datetime`/`time` in-process rather than touching
  the real OS clock, which avoids requiring admin/root privileges and
  avoids destabilizing anything else running on the machine — an actual
  system-clock change was judged too invasive a side effect for an
  automated tool to perform without explicit, scoped consent.
- Perturbation subprocess runner uses `--junitxml` and reads the target
  node id's outcome from the report rather than the process exit code,
  because Order perturbations deliberately run more than one test per
  subprocess (a "pollution" predecessor plus the target) and the exit code
  only reflects the whole session.
- The pytest plugin that applies perturbations (`flake_forensics.perturb.plugin`)
  is loaded per-subprocess via `-p`, never registered as an installed
  entry point — so a plain pytest run of this repo's own suite never
  touches it, and the isolation tests are actually testing the real
  subprocess path, not a mock of it.
- Concurrency fixture deliberately includes a no-op function call between
  the read and the write of the racy increment. Empirically verified (see
  session log) that CPython's eval-breaker is checked at loop backedges and
  call sites but not at arbitrary points inside a straight-line loop body,
  so a bare read-then-write with no call in between never raced on this
  interpreter even at 5,000,000 iterations x 8 threads x low switch
  interval. A call in the gap is also more representative of real
  check-then-act bugs, which usually have an actual function call or I/O
  in between, not adjacent bytecodes.
