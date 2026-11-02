"""Surface an unidentifiable Codex carrier without driving its pane."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_codex_rebind
import _supervisor_herdr_stall
import registry
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "reconcile_replacement_before_identity_refusal",
    "unidentified_codex_row",
]


def reconcile_replacement_before_identity_refusal(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    target: str | None,
    act: bool,
) -> tuple[str | None, RowView | None]:
    """Advance an exact daemon-owned replacement before classifying its successor."""
    if target is None and not _supervisor_herdr_stall.replacement_is_pending(track=track):
        return None, None
    if target is None:
        target = sup.tmux.pane_id(session=session)
    if target is None:
        return None, None
    return target, _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup,
        track=track,
        target=target,
        act=act,
        alert=act,
    )


def unidentified_codex_row(
    *,
    sup: Supervisor,
    track: registry.Track,
    carrier: _supervisor_codex_rebind.UnidentifiedCodexPane,
    act: bool,
) -> RowView:
    """Report the identity refusal once, without touching the carrier's pane."""
    if act:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=carrier.coordinate,
            pane=carrier.coordinate,
            message=(
                f"live Codex carrier process id {carrier.pid} in pane {carrier.coordinate} "
                f"has {carrier.condition}; refusing to identify or drive it"
            ),
            condition="unidentified-session",
        )
    return RowView(
        topic=track.topic,
        repo=track.repo,
        tmux=None,
        ctx=None,
        status="unidentified-session",
        note=_supervisor_codex_rebind.UNIDENTIFIED_NOTE,
    )
