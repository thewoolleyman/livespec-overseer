"""Foreman-owned per-track human-decision escalation markers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import jsonio
import registry
from _supervisor_view import MAX_REASON_IN_ALERT, elide

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "FOREMAN_ESCALATED_STATUS",
    "ForemanEscalation",
    "ForemanEscalationDecision",
    "attention_decision",
    "escalation_path",
    "read_escalation",
    "surface_foreman_escalation_alert",
]

FOREMAN_ESCALATED_STATUS = "foreman-escalated"
_ESCALATION_DIR = "escalations"


@dataclass(frozen=True, kw_only=True)
class ForemanEscalation:
    reason: str | None
    session_identity: str | None = None


@dataclass(frozen=True, kw_only=True)
class ForemanEscalationDecision:
    status: str
    note: str
    active_conditions: set[str]


def escalation_path(*, repo: str, topic: str) -> Path:
    return Path(repo) / "tmp" / "overseer" / "foreman" / _ESCALATION_DIR / f"{topic}.json"


def _read_payload(*, path: Path) -> dict[str, object] | None:
    try:
        parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if jsonio.is_parse_failure(result=parsed):
        return None
    return parsed.unwrap()


def _marker_identity(*, payload: dict[str, object]) -> str | None:
    session_identity = payload.get("session_identity")
    if not isinstance(session_identity, str) or not session_identity.strip():
        return None
    return session_identity.strip()


def _superseded(*, marker_identity: str | None, live_session_identity: str | None) -> bool:
    return (
        marker_identity is not None
        and live_session_identity is not None
        and marker_identity != live_session_identity
    )


def read_escalation(
    *, repo: str, topic: str, live_session_identity: str | None = None
) -> ForemanEscalation | None:
    path = escalation_path(repo=repo, topic=topic)
    if not path.is_file():
        return None
    payload = _read_payload(path=path)
    if payload is None:
        return ForemanEscalation(reason=None)
    if payload.get("resolved") is True:
        return None
    marker_identity = _marker_identity(payload=payload)
    if _superseded(marker_identity=marker_identity, live_session_identity=live_session_identity):
        return None
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return ForemanEscalation(reason=None)
    return ForemanEscalation(reason=reason.strip(), session_identity=marker_identity)


def _note(*, escalation: ForemanEscalation) -> str:
    note = "foreman needs human decision"
    if escalation.reason is not None:
        return f"{note}: {escalation.reason}"
    return note


def attention_decision(
    *, sup: Supervisor, track: registry.Track, session: str, pane: str, act: bool
) -> ForemanEscalationDecision | None:
    escalation = read_escalation(
        repo=track.repo,
        topic=track.topic,
        live_session_identity=track.observed_session_identity,
    )
    if escalation is None:
        return None
    active = (
        surface_foreman_escalation_alert(
            sup=sup, track=track, session=session, pane=pane, escalation=escalation
        )
        if act
        else {FOREMAN_ESCALATED_STATUS}
    )
    return ForemanEscalationDecision(
        status=FOREMAN_ESCALATED_STATUS,
        note=_note(escalation=escalation),
        active_conditions=active,
    )


def surface_foreman_escalation_alert(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    escalation: ForemanEscalation,
) -> set[str]:
    note = _note(escalation=escalation)
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=pane,
        message=(
            "foreman escalation needs human decision: "
            f"{elide(text=note, limit=MAX_REASON_IN_ALERT)} — inspect that pane"
        ),
        condition=FOREMAN_ESCALATED_STATUS,
    )
    return {FOREMAN_ESCALATED_STATUS}
