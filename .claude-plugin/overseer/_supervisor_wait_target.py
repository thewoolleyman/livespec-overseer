"""Report-only attention for wait-premise targets that can no longer be found."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import _supervisor_liveness
import _supervisor_wait_target_sources
import registry
import wait_premises
from _supervisor_view import MAX_REASON_IN_ALERT, elide
from _supervisor_wait_target_status import (
    WAIT_TARGET_MISSING_CONDITION,
    WAIT_TARGET_MISSING_STATUS,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "WAIT_TARGET_MISSING_CONDITION",
    "WAIT_TARGET_MISSING_STATUS",
    "WaitTargetMissingRequest",
    "WaitTargetMissingResult",
    "apply_wait_target_missing_attention",
]


@dataclass(frozen=True, kw_only=True)
class WaitTargetMissingResult:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class WaitTargetMissingRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def _unchanged(*, request: WaitTargetMissingRequest) -> WaitTargetMissingResult:
    return WaitTargetMissingResult(
        status=request.status,
        note=request.note,
        active_conditions=set(request.active_conditions),
    )


def _surface(*, request: WaitTargetMissingRequest, note: str) -> None:
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=(
            f"{elide(text=note, limit=MAX_REASON_IN_ALERT)} - inspect the waiting "
            "session; report-only, no restart authorized"
        ),
        condition=WAIT_TARGET_MISSING_CONDITION,
    )


def apply_wait_target_missing_attention(
    *, request: WaitTargetMissingRequest
) -> WaitTargetMissingResult:
    records = wait_premises.read_wait_premises(repo=request.track.repo, topic=request.track.topic)
    if not records:
        return _unchanged(request=request)
    repo = Path(request.track.repo)
    now = request.obs.observed_at
    cache = request.obs.istate.wait_target_cache
    for record in records:
        key = _supervisor_wait_target_sources.cache_key(record=record)
        entry = _supervisor_wait_target_sources.verify_wait_target_record(
            repo=repo, record=record, cache=cache.get(key), now=now
        )
        cache[key] = entry
        if entry.status != WAIT_TARGET_MISSING_STATUS or entry.note is None:
            continue
        note = _supervisor_liveness.append_note(note=request.note, extra=entry.note)
        if request.act:  # pragma: no branch
            _surface(request=request, note=entry.note)
        return WaitTargetMissingResult(
            status=WAIT_TARGET_MISSING_STATUS,
            note=note,
            active_conditions={*request.active_conditions, WAIT_TARGET_MISSING_CONDITION},
        )
    return _unchanged(request=request)
