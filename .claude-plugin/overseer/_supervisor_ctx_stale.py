"""Context-stale branch of the supervisor decision cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_liveness
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["CtxStaleRequest", "ctx_stale"]


@dataclass(frozen=True, kw_only=True)
class CtxStaleRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    ctx_stale_age: float
    stale_ctx: int
    threshold: int
    act: bool


def ctx_stale(*, request: CtxStaleRequest) -> None:
    if not request.act:
        return
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=(
            f"context unreadable for "
            f"{_supervisor_liveness.age_label(seconds=request.ctx_stale_age)} "
            f"after last known {request.stale_ctx}% at or below {request.threshold}% — "
            "inspect the pane before acting"
        ),
        condition="ctx-stale",
    )
