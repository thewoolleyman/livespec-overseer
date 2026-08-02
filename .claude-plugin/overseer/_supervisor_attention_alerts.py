"""Alert formatting and surfacing for liveness attention."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
from _supervisor_view import MAX_REASON_IN_ALERT, elide

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "ShellAlertRequest",
    "StarvationAlertRequest",
    "shell_evidence_note",
    "starvation_evidence_note",
    "surface_shell_prolonged_alert",
    "surface_starvation_alert",
]


@dataclass(frozen=True, kw_only=True)
class ShellAlertRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    age: float


@dataclass(frozen=True, kw_only=True)
class StarvationAlertRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    age: float
    blocked: str | None
    blocked_age: float | None
    gate: bool
    shell_age: float | None


_SECONDS_PER_MINUTE = 60.0
_SECONDS_PER_HOUR = 3600.0


def age_label(*, seconds: float) -> str:
    clamped = max(0.0, seconds)
    if clamped < _SECONDS_PER_HOUR:
        return f"{int(clamped // _SECONDS_PER_MINUTE)}m"
    return f"{int(clamped // _SECONDS_PER_HOUR)}h"


def shell_evidence_note(*, age: float | None = None) -> str:
    if age is None:
        return "background shell"
    return f"background shell {age_label(seconds=age)}"


def starvation_evidence_note(*, request: StarvationAlertRequest) -> str:
    parts = [f"winddown starved {age_label(seconds=request.age)}"]
    if request.blocked is not None:
        blocked_age = age_label(seconds=request.blocked_age or 0.0)
        parts.append(f"blocked {blocked_age}: {request.blocked}")
    if request.gate:
        parts.append("visible gate")
    if request.shell_age is not None:
        parts.append(shell_evidence_note(age=request.shell_age))
    return "; ".join(parts)


def surface_starvation_alert(*, request: StarvationAlertRequest) -> set[str]:
    note = starvation_evidence_note(request=request)
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=(
            f"wind-down starved ({age_label(seconds=request.age)}): "
            f"{elide(text=note, limit=MAX_REASON_IN_ALERT)} — inspect that pane"
        ),
        condition="winddown-starved",
    )
    return {"winddown-starved"}


def surface_shell_prolonged_alert(*, request: ShellAlertRequest) -> set[str]:
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=(
            f"background shell prolonged ({age_label(seconds=request.age)}): "
            "busy solely on shell evidence with no progress — inspect that pane"
        ),
        condition="shell-prolonged",
    )
    return {"shell-prolonged"}
