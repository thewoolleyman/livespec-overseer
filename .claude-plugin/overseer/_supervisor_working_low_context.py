"""Report-only attention for busy panes below the danger floor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
from _supervisor_config import DANGER_CTX_REMAINING
from _supervisor_view import MAX_REASON_IN_ALERT, elide

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "WORKING_LOW_CONTEXT_CONDITION",
    "WORKING_LOW_CONTEXT_NOTE_PREFIX",
    "WorkingLowContextRequest",
    "WorkingLowContextResult",
    "apply_working_low_context_attention",
]

WORKING_LOW_CONTEXT_CONDITION = "working-low-context"
WORKING_LOW_CONTEXT_NOTE_PREFIX = "working low context"


@dataclass(frozen=True, kw_only=True)
class WorkingLowContextResult:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class WorkingLowContextRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def _condition_now(*, request: WorkingLowContextRequest) -> bool:
    return (
        request.status == "working"
        and request.obs.eff_ctx is not None
        and request.obs.eff_ctx <= DANGER_CTX_REMAINING
        and request.obs.declared is None
    )


def _note(*, request: WorkingLowContextRequest) -> str:
    return (
        f"{WORKING_LOW_CONTEXT_NOTE_PREFIX}: ctx {request.obs.eff_ctx}% "
        f"<= danger {DANGER_CTX_REMAINING}%; undeclared busy pane; report-only"
    )


def _surface(*, request: WorkingLowContextRequest, note: str) -> None:
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=(
            f"{elide(text=note, limit=MAX_REASON_IN_ALERT)} - inspect that pane; "
            "no paste, restart, or keystroke is authorized while it is busy"
        ),
        condition=WORKING_LOW_CONTEXT_CONDITION,
    )


def _maybe_surface(*, request: WorkingLowContextRequest, note: str) -> None:
    if request.act:  # pragma: no branch
        _surface(request=request, note=note)


def apply_working_low_context_attention(
    *, request: WorkingLowContextRequest
) -> WorkingLowContextResult:
    if not _condition_now(request=request):
        return WorkingLowContextResult(
            status=request.status,
            note=request.note,
            active_conditions=set(request.active_conditions),
        )
    extra = _note(request=request)
    note = extra if request.note is None else f"{request.note}; {extra}"
    _maybe_surface(request=request, note=note)
    return WorkingLowContextResult(
        status=request.status,
        note=note,
        active_conditions={*request.active_conditions, WORKING_LOW_CONTEXT_CONDITION},
    )
