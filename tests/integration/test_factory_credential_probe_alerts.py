"""Integration coverage for factory-credential probe alerts.

This starts with ``## Scenario: A persisting condition is not re-alerted before
the repeat interval`` from ``SPECIFICATION/scenarios.md``.  The test imports
the production boundary inside the test body: until that boundary ships, the
failure is a specific assertion rather than an import-time collection error.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

__all__: list[str] = []

pytestmark = pytest.mark.integration

_PACKAGE = Path(__file__).resolve().parents[2] / "overseer"


def _factory_credential_probe():
    """Return the shipped factory-credential probe boundary once it exists."""
    module_path = _PACKAGE / "caam_factory_credential_probe.py"
    assert module_path.is_file(), (
        "overseer/caam_factory_credential_probe.py has not shipped; the integration "
        "scenario cannot drive the factory-credential probe or its alert-repeat state"
    )
    return importlib.import_module("caam_factory_credential_probe")


def test_a_persisting_unusable_factory_credential_is_not_realerted_before_its_repeat_interval():
    """A one-hour-old alert remains quiet when its configured interval is six hours."""
    probe = _factory_credential_probe()

    alerts: list[str] = []
    reports = probe.run_once(
        now=7_200.0,
        credentials=(
            probe.FactoryCredential(label="factory-a", tenant="tenant-a", location="unused"),
        ),
        prior_conditions={
            "tenant-a/factory-a": probe.AlertCondition(verdict="unusable", alerted_at=3_600.0)
        },
        repeat_interval_seconds=21_600.0,
        read_credential=lambda *, location: "credential-material",
        observe=lambda *, credential: probe.ProbeReading(weekly_remaining=0.0),
        notify=alerts.append,
    )

    assert reports["tenant-a/factory-a"].verdict == "unusable"
    assert alerts == []
