"""Isolation fixture for the IO-latency dimension (socket target). NOT
collected by the main suite.

Connects to a local server socket that accepts immediately; under the
default (unpatched) `socket.socket.connect` this completes in well under a
millisecond. Under injected connect delay, it blows the budget.
"""

import socket
import time

BUDGET_SECONDS = 0.2


def test_local_connect_completes_within_budget():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    try:
        start = time.monotonic()
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(5.0)
        try:
            client.connect(("127.0.0.1", port))
            conn, _ = server.accept()
            conn.close()
        finally:
            client.close()
        elapsed = time.monotonic() - start
    finally:
        server.close()

    assert elapsed < BUDGET_SECONDS
