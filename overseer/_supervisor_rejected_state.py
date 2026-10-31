"""Reject malformed state declarations without clobbering a later valid write."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import _supervisor_observe
import registry
import signals
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["reject_malformed_state"]


def reject_malformed_state(
    *, sup: Supervisor, track: registry.Track, obs: Observation, session: str, pane: str, act: bool
) -> Observation:
    """Move a still-observed malformed declaration aside before wrap-up composition."""
    declared = obs.declared
    archived = (registry.norm(repo=track.repo), track.topic) in sup.archived_live
    rejected_value = signals.rejected_value(repo=track.repo, topic=track.topic)
    if (
        not act
        or not obs.malformed
        or declared is None
        or declared.token == signals.STATE_PATH_MISMATCH
        or archived
    ):
        return dataclasses.replace(obs, rejected_value=rejected_value)
    current = signals.read_state(repo=track.repo, topic=track.topic)
    if current is None or (current.token, current.mtime) != (declared.token, declared.mtime):
        refreshed = _supervisor_observe.observe(
            sup=sup, track=track, session=session, target=pane, key=(track.repo, track.topic)
        )
        return dataclasses.replace(refreshed, rejected_value=rejected_value)
    try:
        _ = signals.state_path(repo=track.repo, topic=track.topic).replace(
            signals.rejected_state_path(repo=track.repo, topic=track.topic)
        )
    except OSError as exc:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=pane,
            message=f"could not reject malformed state file {declared.token!r}: {exc}",
            condition="malformed-state-rejection-failed",
        )
        return dataclasses.replace(obs, rejected_value=rejected_value)
    return dataclasses.replace(
        obs,
        declared=None,
        malformed=False,
        blocked=None,
        acked=False,
        ready=False,
        rejected_value=signals.rejected_value(repo=track.repo, topic=track.topic),
        rejected_from_malformed=declared.token,
    )
