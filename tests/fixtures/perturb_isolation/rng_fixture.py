"""Isolation fixture for the RNG dimension. NOT collected by the main suite
(see tests/fixtures/corpus/unseeded_randomness_01.py for why).

Passes iff the global `random` module was seeded to exactly 1234 and this
is the first draw made against it in this process. Under any unseeded
(auto-random) process, or a process seeded to a different value, this fails
with overwhelming probability.
"""

import random

# random.seed(1234); random.random() -- pinned for CPython's Mersenne
# Twister, which has been stable across the versions this project targets.
EXPECTED_FIRST_DRAW = 0.9664535356921388


def test_seed_1234_first_draw():
    assert random.random() == EXPECTED_FIRST_DRAW
