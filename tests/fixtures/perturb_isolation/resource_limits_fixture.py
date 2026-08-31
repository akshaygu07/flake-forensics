"""Isolation fixture for the Resource-limits dimension. NOT collected by the
main suite. POSIX only (see run_resource_limits' docstring for why).

Opens more file descriptors than a constrained RLIMIT_NOFILE allows. Under
the default limit (usually >= 1024) this passes easily; under a low
RLIMIT_NOFILE it hits EMFILE partway through.
"""

import os

FILE_COUNT = 50


def test_open_many_files_within_limit():
    handles = []
    try:
        for _ in range(FILE_COUNT):
            handles.append(open(os.devnull))
    finally:
        for h in handles:
            h.close()
