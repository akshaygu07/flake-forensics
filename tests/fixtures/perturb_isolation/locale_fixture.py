"""Isolation fixture for the Filesystem-state dimension (locale). NOT
collected by the main suite.

Passes iff the active locale formats a float with a dot decimal separator
(the "C"/"en_US"-style default). Under a locale like "de_DE.UTF-8", which
uses a comma, this fails — a classic EXTERNAL_STATE-flavored bug (code that
assumes a fixed decimal separator).
"""

import locale


def test_decimal_separator_is_dot():
    formatted = locale.format_string("%.2f", 1234.5)
    assert formatted == "1234.50"
