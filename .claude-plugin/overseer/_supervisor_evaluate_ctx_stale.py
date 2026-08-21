"""Stale-context idle branch for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_ctx_stale
import _supervisor_liveness
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["CtxStaleDecision", "CtxStaleRequest", "ctx_stale_decision"]


@dataclass(frozen=True, kw_only=True)
class CtxStaleDecision:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class CtxStaleRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    target: str
    ctx_stale_age: float
    stale_ctx: int
    threshold: int
    ctx_stale_note: str | None
    note: str | None
    act: bool


def ctx_stale_decision(*, request: CtxStaleRequest) -> CtxStaleDecision:
    note = _supervisor_liveness.append_note(note=request.note, extra=request.ctx_stale_note)
    _supervisor_ctx_stale.ctx_stale(
        request=_supervisor_ctx_stale.CtxStaleRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.target,
            ctx_stale_age=request.ctx_stale_age,
            stale_ctx=request.stale_ctx,
            threshold=request.threshold,
            act=request.act,
        )
    )
    return CtxStaleDecision(
        status="ctx-stale",
        note=note,
        active_conditions={"ctx-stale"},
    )
