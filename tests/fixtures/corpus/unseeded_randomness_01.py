"""Synthetic corpus fixture — NOT collected by the main test suite.

This file intentionally does not match pytest's default `test_*.py`
collection pattern under `tests/`, so it never runs as part of `flake
forensics`'s own CI. It is a labeled example for the perturbation harness
(Phase 1) and classifier (Phase 2) to run against, not a test of this repo.

label: UNSEEDED_RANDOMNESS
approx_flake_rate: 0.5
notes: fails whenever the unseeded global RNG draws >= 0.5; freezing the
    seed should drive the observed flake rate to 0 or 1 depending on seed.
"""

import random


def test_low_roll_wins():
    assert random.random() < 0.5
