"""Surface an unidentifiable Codex carrier without driving its pane."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _herdr_replacement_store
import _supervisor_codex_rebind
import herdr_identity
import registry
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["preflight_unidentified", "unidentified_codex_row"]


def preflight_unidentified(
    *, sup: Supervisor, track: registry.Track, target: str, act: bool
) -> RowView | None:
    """Refuse an unidentified carrier unless a durable replacement owns its pane."""
    if _active_herdr_replacement(track=track, target=target):
        return None
    carrier = _supervisor_codex_rebind.unidentified_codex_pane(sup=sup, track=track)
    if carrier is None:
        return None
    return unidentified_codex_row(sup=sup, track=track, carrier=carrier, act=act)


def _active_herdr_replacement(*, track: registry.Track, target: str) -> bool:
    """Whether this pane is owned by an unfinished durable replacement."""
    if herdr_identity.decode_target(value=target).herdr is None:
        return False
    try:
        transaction = _herdr_replacement_store.read_transaction(
            path=(
                _herdr_replacement_store.scratch_path(track=track)
                / _herdr_replacement_store.RECORD_NAME
            )
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return False
    return (
        transaction is not None
        and transaction.get("target") == target
        and transaction.get("phase") not in {None, "completed"}
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
