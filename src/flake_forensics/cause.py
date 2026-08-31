from __future__ import annotations

from enum import Enum


class Cause(str, Enum):
    """The eight cause classes a fingerprint can be classified into.

    UNKNOWN is first-class and expected to be returned often: a confident
    wrong guess is worse than an honest "I can't tell yet".
    """

    ORDER_DEPENDENT = "ORDER_DEPENDENT"
    TIME_DEPENDENT = "TIME_DEPENDENT"
    CONCURRENCY = "CONCURRENCY"
    IO_TIMING = "IO_TIMING"
    UNSEEDED_RANDOMNESS = "UNSEEDED_RANDOMNESS"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    EXTERNAL_STATE = "EXTERNAL_STATE"
    UNKNOWN = "UNKNOWN"
