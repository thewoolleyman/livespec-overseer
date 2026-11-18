"""Judge factory credentials and drive the alert lifecycle their verdicts imply.

The scheduled pass keeps the alert conditions outside this module and supplies
them on each call; this module only decides.  A rate-limited or failed provider
read is INCONCLUSIVE and never alerts, because the usage endpoint backs off a
repeatedly read token and its refusal is not evidence that a credential is
exhausted.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Final

__all__: list[str] = [
    "INCONCLUSIVE",
    "UNUSABLE",
    "USABLE",
    "AlertCondition",
    "FactoryCredential",
    "Observer",
    "ProbePass",
    "ProbeReading",
    "ProbeReport",
    "render_report",
    "run_once",
]

USABLE: Final = "usable"
UNUSABLE: Final = "unusable"
INCONCLUSIVE: Final = "inconclusive"


@dataclass(frozen=True, kw_only=True)
class FactoryCredential:
    """A configured factory credential and the location from which to read it."""

    label: str
    tenant: str
    location: str

    @property
    def key(self) -> str:
        """Return the stable identity used for conditions and reports."""
        return f"{self.tenant}/{self.label}"


@dataclass(frozen=True, kw_only=True)
class ProbeReading:
    """One read-only authenticated reading, or the reason none could be taken."""

    unauthenticated: bool = False
    inconclusive: bool = False
    weekly_remaining: float | None = None
    short_window_remaining: float | None = None


@dataclass(frozen=True, kw_only=True)
class AlertCondition:
    """An unusable credential whose onset alert was delivered."""

    started_at: float
    alerted_at: float


@dataclass(frozen=True, kw_only=True)
class ProbeReport:
    """One credential's reportable verdict."""

    key: str
    verdict: str
    probed_at: float


@dataclass(frozen=True, kw_only=True)
class ProbePass:
    """The reports of one probe pass, the conditions to remember, and failed alerts."""

    reports: tuple[ProbeReport, ...]
    conditions: dict[str, AlertCondition]
    failed_alerts: tuple[str, ...]


Observer = Callable[..., ProbeReading]
Notifier = Callable[..., bool]


def run_once(
    *,
    now: float,
    credentials: tuple[FactoryCredential, ...],
    prior: Mapping[str, AlertCondition],
    repeat_interval_seconds: float,
    observe: Observer,
    notify: Notifier,
) -> ProbePass:
    """Probe each credential; an alert is delivered only when its lifecycle makes one due.

    `observe` raises OSError for a credential that cannot be read from its
    location.  `notify` returns whether the alert was delivered; an undelivered
    alert leaves the condition as it was, so the next pass retries it.
    """
    reports: list[ProbeReport] = []
    conditions: dict[str, AlertCondition] = {}
    failed: list[str] = []
    for credential in credentials:
        verdict = _verdict(credential=credential, observe=observe)
        reports.append(ProbeReport(key=credential.key, verdict=verdict, probed_at=now))
        condition, delivered = _lifecycle(
            credential=credential,
            verdict=verdict,
            prior=prior.get(credential.key),
            now=now,
            repeat_interval_seconds=repeat_interval_seconds,
            notify=notify,
        )
        if condition is not None:
            conditions[credential.key] = condition
        if not delivered:
            failed.append(credential.key)
    return ProbePass(reports=tuple(reports), conditions=conditions, failed_alerts=tuple(failed))


def render_report(
    *,
    reports: tuple[ProbeReport, ...],
    failed_alerts: tuple[str, ...],
    push_channel_configured: bool,
) -> tuple[str, ...]:
    """Render each credential's label, tenant, last probe time and verdict, then delivery state."""
    lines = [
        f"{report.key}: {report.verdict} (probed {_when(at=report.probed_at)})"
        for report in sorted(reports, key=lambda report: report.key)
    ]
    if not push_channel_configured:
        lines.append("alerts cannot be delivered: no push channel configured")
    lines.extend(f"alert delivery failed for {key}; retrying next pass" for key in failed_alerts)
    return tuple(lines)


def _verdict(*, credential: FactoryCredential, observe: Observer) -> str:
    try:
        reading = observe(credential=credential)
    except OSError:
        return UNUSABLE
    if reading.inconclusive:
        return INCONCLUSIVE
    exhausted = any(
        figure is not None and figure <= 0
        for figure in (reading.weekly_remaining, reading.short_window_remaining)
    )
    if reading.unauthenticated or exhausted:
        return UNUSABLE
    return USABLE


def _lifecycle(
    *,
    credential: FactoryCredential,
    verdict: str,
    prior: AlertCondition | None,
    now: float,
    repeat_interval_seconds: float,
    notify: Notifier,
) -> tuple[AlertCondition | None, bool]:
    """Return the condition to remember and whether no alert is left undelivered."""
    subject = f"{credential.label} for tenant {credential.tenant}"
    if verdict == INCONCLUSIVE:
        return prior, True
    if verdict == USABLE:
        if prior is None:
            return None, True
        sent = notify(message=f"factory credential recovered: {subject}")
        return (None if sent else prior), sent
    if prior is None:
        sent = notify(message=f"factory credential unusable since {_when(at=now)}: {subject}")
        return (AlertCondition(started_at=now, alerted_at=now) if sent else None), sent
    if now - prior.alerted_at < repeat_interval_seconds:
        return prior, True
    sent = notify(
        message=f"factory credential still unusable since {_when(at=prior.started_at)}: {subject}"
    )
    return (replace(prior, alerted_at=now) if sent else prior), sent


def _when(*, at: float) -> str:
    return datetime.fromtimestamp(at, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
