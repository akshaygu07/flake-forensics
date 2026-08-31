"""Isolation fixture for the Order dimension. NOT collected by the main
suite.

test_b_depends_on_pollution passes iff test_a_pollutes already ran earlier
in the same process (module-level state leaking between tests, a classic
order-dependent flake). Run alone, it fails.
"""

_state: list[str] = []


def test_a_pollutes():
    _state.append("polluted")
    assert True


def test_b_depends_on_pollution():
    assert _state == ["polluted"]
