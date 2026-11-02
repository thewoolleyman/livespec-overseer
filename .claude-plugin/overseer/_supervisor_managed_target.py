"""Prove a resolved terminal target before the supervisor drives it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_codex_misnamed
import _supervisor_herdr_stall
import _supervisor_observe
import herdr_identity
import registry
from _supervisor_config import track_key
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["EvaluateTarget", "evaluate_managed_target"]


@dataclass(frozen=True, kw_only=True)
class EvaluateTarget:
    track: registry.Track
    repo: str
    topic: str
    session: str
    key: tuple[str, str]
    pane: str


def evaluate_managed_target(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    target: str,
    act: bool,
) -> RowView | EvaluateTarget:
    """Reconcile a durable replacement, then prove the pane before supervision."""
    held = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup,
        track=track,
        target=target,
        act=act,
        alert=act,
    )
    if held is not None:
        return held
    if _unproven_herdr_target(sup=sup, track=track, session=session, target=target) or not (
        _supervisor_observe.pane_is_managed(
            sup=sup,
            target=target,
            repo=track.repo,
            topic=track.topic,
            session=session,
        )
    ):
        return _supervisor_codex_misnamed.gone_row(
            sup=sup,
            track=track,
            session=session,
            act=act,
        )
    return EvaluateTarget(
        track=track,
        repo=track.repo,
        topic=track.topic,
        session=session,
        key=track_key(repo=track.repo, topic=track.topic),
        pane=target,
    )


def _unproven_herdr_target(
    *, sup: Supervisor, track: registry.Track, session: str, target: str
) -> bool:
    """Whether a Herdr row without a process identity fails to name its topic."""
    if not session.startswith(herdr_identity.HERDR_SCHEME):
        return False
    if (track.observed_session_identity or "").startswith("claude:"):
        return False
    if track.topic in sup.claude_names_by_session.get(session, set()):
        return False
    return not _supervisor_observe.is_codex_track(
        sup=sup,
        session=session,
        repo=track.repo,
        topic=track.topic,
        target=target,
    )
