"""Self-adoption helper for the per-repo foreman runtime."""

from __future__ import annotations

import os
from pathlib import Path

import registry
from _runtime_registration_profile import registration_model_profile
from _supervisor_config import iso_now
from foreman_runtime_identity import canonical_session_name

__all__: list[str] = ["register_foreman_track"]


def register_foreman_track(
    *,
    repo: str | os.PathLike[str],
    epic: str | None = None,
    store_path: str | os.PathLike[str] | None = None,
) -> registry.Track:
    repo_path = Path(repo).resolve()
    session_name = canonical_session_name(repo=repo_path)
    added_at = iso_now()
    track = registry.ForemanSeat(
        topic=session_name,
        repo=str(repo_path),
        tmux=session_name,
        epic=epic or registry.unresolved_plan_epic(topic=session_name),
        added_at=added_at,
        model_profile=registration_model_profile(),
    )
    _ = registry.upsert_mapping(track=track, store_path=store_path, added_at=added_at)
    return track
