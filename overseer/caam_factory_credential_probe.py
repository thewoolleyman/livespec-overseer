"""Probe factory credentials and describe their alert lifecycle.

The scheduled credential operation keeps prior alert conditions outside this
module and supplies them on each pass.  Keeping the boundary pure makes a
rate-limited request explicitly inconclusive instead of mistaking it for an
unusable credential.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

__all__: list[str] = [
    "AlertCondition",
    "FactoryCredential",
    "ProbeReading",
    "ProbeReport",
    "render_report",
    "run_once",
]


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
    """The usable portion of one provider probe."""

    weekly_remaining: float | None = None
    rate_limited: bool = False


@dataclass(frozen=True, kw_only=True)
class AlertCondition:
    """The last alert-delivered verdict for one credential."""

    verdict: str
    alerted_at: float


@dataclass(frozen=True, kw_only=True)
class ProbeReport:
    """One credential's current, reportable probe verdict."""

    verdict: str


CredentialReader = Callable[..., str]
ProbeObserver = Callable[..., ProbeReading]
Notifier = Callable[[str], None]


def run_once(  # noqa: PLR0913 - the seams are independently supplied by the pass
    *,
    now: float,
    credentials: tuple[FactoryCredential, ...],
    prior_conditions: Mapping[str, AlertCondition],
    repeat_interval_seconds: float,
    read_credential: CredentialReader,
    observe: ProbeObserver,
    notify: Notifier,
) -> dict[str, ProbeReport]:
    """Probe configured credentials and deliver only due failure or recovery alerts."""
    reports: dict[str, ProbeReport] = {}
    for credential in credentials:
        report = _probe(
            credential=credential,
            read_credential=read_credential,
            observe=observe,
        )
        reports[credential.key] = report
        _notify_if_due(
            credential=credential,
            report=report,
            prior=prior_conditions.get(credential.key),
            now=now,
            repeat_interval_seconds=repeat_interval_seconds,
            notify=notify,
        )
    return reports


def render_report(*, reports: Mapping[str, ProbeReport], push_channel_configured: bool) -> str:
    """Render a stable, operator-facing credential report."""
    lines = [f"{key}: {report.verdict}" for key, report in sorted(reports.items())]
    lines.extend(
        {
            True: (),
            False: ("alerts cannot be delivered: no push channel configured",),
        }[push_channel_configured]
    )
    return "\n".join(lines)


def _probe(
    *, credential: FactoryCredential, read_credential: CredentialReader, observe: ProbeObserver
) -> ProbeReport:
    try:
        _ = read_credential(location=credential.location)
    except OSError:
        return ProbeReport(verdict="unusable")
    reading = observe(credential=credential)
    if reading.rate_limited:
        return ProbeReport(verdict="inconclusive")
    if reading.weekly_remaining is None or reading.weekly_remaining <= 0:
        return ProbeReport(verdict="unusable")
    return ProbeReport(verdict="usable")


def _notify_if_due(
    *,
    credential: FactoryCredential,
    report: ProbeReport,
    prior: AlertCondition | None,
    now: float,
    repeat_interval_seconds: float,
    notify: Notifier,
) -> None:
    if report.verdict == "inconclusive":
        return
    if report.verdict == "usable":
        _deliver(
            notify=notify,
            messages=_when(
                due=getattr(prior, "verdict", "") == "unusable",
                message=(
                    f"factory credential recovered: {credential.label} "
                    f"for tenant {credential.tenant}"
                ),
            ),
        )
        return
    if prior is None or prior.verdict != report.verdict:
        notify(f"factory credential unusable: {credential.label} for tenant {credential.tenant}")
        return
    _deliver(
        notify=notify,
        messages=_when(
            due=now - prior.alerted_at >= repeat_interval_seconds,
            message=(
                f"factory credential still unusable: {credential.label} "
                f"for tenant {credential.tenant}"
            ),
        ),
    )


def _when(*, due: bool, message: str) -> tuple[str, ...]:
    """Return a one-message sequence precisely when an alert is due."""
    return (message,)[: int(due)]


def _deliver(*, notify: Notifier, messages: tuple[str, ...]) -> None:
    """Deliver every already-authorized alert message."""
    for message in messages:
        notify(message)
