"""Integration coverage for factory-credential probe alerts.

These tests exercise the five factory-credential alert scenarios in
``SPECIFICATION/scenarios.md``.  The production boundary is imported inside a
helper so an absent implementation is reported as an assertion failure rather
than as a collection failure.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

__all__: list[str] = []

pytestmark = pytest.mark.integration

_PACKAGE = Path(__file__).resolve().parents[2] / "overseer"
_CREDENTIAL = ("factory-a", "tenant-a", "unused")


def _factory_credential_probe():
    """Return the shipped factory-credential probe boundary once it exists."""
    module_path = _PACKAGE / "caam_factory_credential_probe.py"
    assert module_path.is_file(), (
        "overseer/caam_factory_credential_probe.py has not shipped; the integration "
        "scenarios cannot drive the factory-credential probe and alert lifecycle"
    )
    return importlib.import_module("caam_factory_credential_probe")


def _credential(probe):
    label, tenant, location = _CREDENTIAL
    return probe.FactoryCredential(label=label, tenant=tenant, location=location)


def test_a_persisting_unusable_factory_credential_is_not_realerted_before_its_repeat_interval():
    """A one-hour-old alert remains quiet when its configured interval is six hours."""
    probe = _factory_credential_probe()
    alerts: list[str] = []

    reports = probe.run_once(
        now=7_200.0,
        credentials=(_credential(probe),),
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


def test_a_rate_limited_factory_credential_probe_is_inconclusive_and_not_alerted():
    """A rate limit produces an inconclusive report without a push alert."""
    probe = _factory_credential_probe()
    alerts: list[str] = []

    reports = probe.run_once(
        now=7_200.0,
        credentials=(_credential(probe),),
        prior_conditions={},
        repeat_interval_seconds=21_600.0,
        read_credential=lambda *, location: "credential-material",
        observe=lambda *, credential: probe.ProbeReading(rate_limited=True),
        notify=alerts.append,
    )

    assert reports["tenant-a/factory-a"].verdict == "inconclusive"
    assert alerts == []


def test_an_unreadable_factory_credential_is_unusable_and_alerted_with_its_identity():
    """An unreadable configured location is a reportable unusable credential."""
    probe = _factory_credential_probe()
    alerts: list[str] = []

    reports = probe.run_once(
        now=7_200.0,
        credentials=(_credential(probe),),
        prior_conditions={},
        repeat_interval_seconds=21_600.0,
        read_credential=lambda *, location: (_ for _ in ()).throw(PermissionError(location)),
        observe=lambda *, credential: probe.ProbeReading(weekly_remaining=1.0),
        notify=alerts.append,
    )

    assert reports["tenant-a/factory-a"].verdict == "unusable"
    assert len(alerts) == 1
    assert "factory-a" in alerts[0]
    assert "tenant-a" in alerts[0]


def test_a_recovered_factory_credential_sends_exactly_one_recovery_alert():
    """A usable reading after an unusable alert reports one recovery notification."""
    probe = _factory_credential_probe()
    alerts: list[str] = []

    reports = probe.run_once(
        now=7_200.0,
        credentials=(_credential(probe),),
        prior_conditions={
            "tenant-a/factory-a": probe.AlertCondition(verdict="unusable", alerted_at=3_600.0)
        },
        repeat_interval_seconds=21_600.0,
        read_credential=lambda *, location: "credential-material",
        observe=lambda *, credential: probe.ProbeReading(weekly_remaining=1.0),
        notify=alerts.append,
    )

    assert reports["tenant-a/factory-a"].verdict == "usable"
    assert len(alerts) == 1
    assert "recovered" in alerts[0]


def test_a_report_states_when_no_push_channel_is_configured():
    """The report makes an absent delivery channel visible to the operator."""
    probe = _factory_credential_probe()

    report = probe.render_report(
        reports={"tenant-a/factory-a": probe.ProbeReport(verdict="usable")},
        push_channel_configured=False,
    )

    assert "alerts cannot be delivered" in report
