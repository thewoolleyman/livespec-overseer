"""Integration-tier coverage for staged startup-transient rendezvous behavior.

These controls drive the live-herdr fixture boundary rather than a product helper:
the fixture is the subject whose bounded observation must remain load-independent.
"""

from __future__ import annotations

from test_herdr_live_observations import PaneReadiness


def test_scenario_live_herdr_fixture_owns_a_startup_transient_release() -> None:
    """The observation fixture carries the release rendezvous into its gate."""
    assert "release" in PaneReadiness.__dataclass_fields__
