"""The rotation pass's factory-credential probe stage.

Reads the operator's PROBE LIST (labels, owning tenants and locations -- never
credential values), probes each listed credential once per probe interval with
the same read-only usage read the pass already makes, delivers the alerts the
verdicts make due through the operator's ntfy push channel, and reports every
probed credential.  The pure judgement and alert lifecycle live in
``caam_factory_credential_probe``; this module is how the pass reaches the host.

Nothing here refreshes, rewrites or rotates a probed credential, and nothing
feeds the interactive account's selection.  What the stage remembers between
passes -- when it last probed, what it last found, and which conditions have
been alerted -- lives in its own owner-only file rather than the rotation state.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import jsonio
from caam_anthropic_decide import UsageFetcher
from caam_decide_context import DecisionContext
from caam_delivery_push_sweep import Post, ntfy_push, ntfy_url
from caam_factory_credential_probe import (
    AlertCondition,
    FactoryCredential,
    ProbePass,
    ProbeReading,
    ProbeReport,
    render_report,
    run_once,
)

__all__: list[str] = ["CONDITIONS_REL", "PROBE_LIST_REL", "observe_pass_factory_probes"]

PROBE_LIST_REL: Final = Path(".config/caam-usage-rotate/factory-probe-list.json")
CONDITIONS_REL: Final = Path(".local/state/caam-usage-rotate/factory-probe-conditions.json")
_DEFAULT_PROBE_INTERVAL_S: Final = 3600.0
_DEFAULT_REPEAT_INTERVAL_S: Final = 21600.0
_MALFORMED: Final = "factory probe list is malformed; no credential was probed"
# A refusal is evidence of an unusable credential only when it says the request was
# unauthenticated; every other refusal or failure is inconclusive and never alerts.
_UNAUTHENTICATED: Final = re.compile(
    r"HTTP 40[13]|authenticat|unauthori[sz]ed|token (has )?expired|no token in snapshot",
    re.IGNORECASE,
)


@dataclass(frozen=True, kw_only=True)
class _ProbeList:
    credentials: tuple[FactoryCredential, ...]
    probe_interval_seconds: float
    repeat_interval_seconds: float


@dataclass(frozen=True, kw_only=True)
class _Memory:
    last_probe_at: float | None
    reports: tuple[ProbeReport, ...]
    conditions: dict[str, AlertCondition]
    failed_alerts: tuple[str, ...]


def observe_pass_factory_probes(
    *, context: DecisionContext, fetcher: UsageFetcher, post: Post | None
) -> None:
    """Run the stage's pass and write its report lines; silent when no list is configured."""
    for line in _factory_probe_lines(
        home=context.home,
        now=context.now,
        dry_run=context.flags.dry_run,
        fetcher=fetcher,
        post=post,
    ):
        context.stdout(line)


def _factory_probe_lines(
    *, home: Path, now: float, dry_run: bool, fetcher: UsageFetcher, post: Post | None
) -> tuple[str, ...]:
    """Run the stage's pass and return its report lines; nothing when no list is configured."""
    try:
        text = (home / PROBE_LIST_REL).read_text(encoding="utf-8")
    except OSError:
        return ()
    if dry_run:
        return ()
    probe_list = _parse_probe_list(text=text)
    if probe_list is None:
        return (_MALFORMED,)
    configured = ntfy_url(home=home) is not None
    memory = _load_memory(home=home)
    if _due(memory=memory, now=now, probe_list=probe_list):
        result = _probe(
            home=home, now=now, probe_list=probe_list, memory=memory, fetcher=fetcher, post=post
        )
        memory = _Memory(
            last_probe_at=now,
            reports=result.reports,
            conditions=result.conditions,
            failed_alerts=result.failed_alerts if configured else (),
        )
        _save_memory(home=home, memory=memory)
    return render_report(
        reports=memory.reports,
        failed_alerts=memory.failed_alerts,
        push_channel_configured=configured,
    )


def _due(*, memory: _Memory, now: float, probe_list: _ProbeList) -> bool:
    if memory.last_probe_at is None or memory.failed_alerts:
        return True
    return now - memory.last_probe_at >= probe_list.probe_interval_seconds


def _probe(
    *,
    home: Path,
    now: float,
    probe_list: _ProbeList,
    memory: _Memory,
    fetcher: UsageFetcher,
    post: Post | None,
) -> ProbePass:
    def observe(*, credential: FactoryCredential) -> ProbeReading:
        location = Path(credential.location)
        _ = location.read_bytes()
        usage, reason = fetcher(creds_path=location, now=now)
        if usage is None:
            refused = _UNAUTHENTICATED.search(reason or "") is not None
            return ProbeReading(unauthenticated=refused, inconclusive=not refused)
        return ProbeReading(
            weekly_remaining=usage.seven_day_remaining,
            short_window_remaining=usage.five_hour_remaining
            if usage.short_window_present
            else None,
        )

    def notify(*, message: str) -> bool:
        return ntfy_push(home=home, message=message, post=post).startswith("sent")

    return run_once(
        now=now,
        credentials=probe_list.credentials,
        prior=memory.conditions,
        repeat_interval_seconds=probe_list.repeat_interval_seconds,
        observe=observe,
        notify=notify,
    )


def _parse_probe_list(*, text: str) -> _ProbeList | None:
    parsed = jsonio.parse_object(text=text)
    body = None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
    entries = None if body is None else jsonio.as_list(value=body.get("credentials"))
    if body is None or entries is None:
        return None
    credentials = tuple(_credential(entry=entry) for entry in entries)
    probe_interval = _interval(
        body=body, key="probe_interval_seconds", default=_DEFAULT_PROBE_INTERVAL_S
    )
    repeat_interval = _interval(
        body=body, key="repeat_interval_seconds", default=_DEFAULT_REPEAT_INTERVAL_S
    )
    if None in credentials or probe_interval is None or repeat_interval is None:
        return None
    return _ProbeList(
        credentials=tuple(credential for credential in credentials if credential is not None),
        probe_interval_seconds=probe_interval,
        repeat_interval_seconds=repeat_interval,
    )


def _credential(*, entry: object) -> FactoryCredential | None:
    body = jsonio.as_object(value=entry) or {}
    label, tenant, location = body.get("label"), body.get("tenant"), body.get("location")
    if isinstance(label, str) and isinstance(tenant, str) and isinstance(location, str):
        return FactoryCredential(label=label, tenant=tenant, location=location)
    return None


def _interval(*, body: dict[str, object], key: str, default: float) -> float | None:
    return default if key not in body else jsonio.as_float(value=body[key])


def _load_memory(*, home: Path) -> _Memory:
    empty = _Memory(last_probe_at=None, reports=(), conditions={}, failed_alerts=())
    try:
        parsed = jsonio.parse_object(text=(home / CONDITIONS_REL).read_text(encoding="utf-8"))
    except OSError:
        return empty
    body = None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
    if body is None:
        return empty
    conditions = jsonio.as_object(value=body.get("conditions")) or {}
    return _Memory(
        last_probe_at=jsonio.as_float(value=body.get("last_probe_at")),
        reports=tuple(
            _report(entry=entry) for entry in jsonio.as_list(value=body.get("reports")) or []
        ),
        conditions={key: _condition(entry=entry) for key, entry in conditions.items()},
        failed_alerts=tuple(
            str(key) for key in jsonio.as_list(value=body.get("failed_alerts")) or []
        ),
    )


def _report(*, entry: object) -> ProbeReport:
    body = jsonio.as_object(value=entry) or {}
    return ProbeReport(
        key=str(body.get("key")),
        verdict=str(body.get("verdict")),
        probed_at=jsonio.as_float(value=body.get("probed_at")) or 0.0,
    )


def _condition(*, entry: object) -> AlertCondition:
    body = jsonio.as_object(value=entry) or {}
    return AlertCondition(
        started_at=jsonio.as_float(value=body.get("started_at")) or 0.0,
        alerted_at=jsonio.as_float(value=body.get("alerted_at")) or 0.0,
    )


def _save_memory(*, home: Path, memory: _Memory) -> None:
    path = home / CONDITIONS_REL
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "last_probe_at": memory.last_probe_at,
        "reports": [
            {"key": report.key, "verdict": report.verdict, "probed_at": report.probed_at}
            for report in memory.reports
        ],
        "conditions": {
            key: {"started_at": condition.started_at, "alerted_at": condition.alerted_at}
            for key, condition in memory.conditions.items()
        },
        "failed_alerts": list(memory.failed_alerts),
    }
    temporary = path.with_name(path.name + ".tmp")
    _ = temporary.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    temporary.chmod(0o600)
    _ = temporary.replace(path)
