"""Observation-side helpers for the supervisor evaluation cascade."""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["record_observed_session_identity"]


def record_observed_session_identity(
    *, sup: Supervisor, track: registry.Track, obs: Observation, act: bool
) -> None:
    if not act or obs.session_identity is None:
        return
    _ = registry.record_observed_session_identity(
        repo=track.repo,
        topic=track.topic,
        session_identity=obs.session_identity,
        store_path=sup.store_path,
    )
