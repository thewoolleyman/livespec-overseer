"""Self-adoption helper for the per-repo grooming operation."""

from __future__ import annotations

import os
from pathlib import Path

import registry

__all__: list[str] = ["canonical_session_name", "register_grooming_track"]


def canonical_session_name(*, repo: str | os.PathLike[str]) -> str:
    """The reserved tmux/topic identity for a repo's grooming pass."""
    return f"{Path(repo).resolve().name}-grooming"


def register_grooming_track(
    *,
    repo: str | os.PathLike[str],
    epic: str | None = None,
    store_path: str | os.PathLike[str] | None = None,
) -> registry.Track:
    """Ensure the grooming pass is supervised before it starts the drain."""
    repo_path = Path(repo).resolve()
    session_name = canonical_session_name(repo=repo_path)
    track = registry.GroomingSeat(
        topic=session_name,
        repo=str(repo_path),
        tmux=session_name,
        epic=epic or registry.unresolved_plan_epic(topic=session_name),
    )
    registry.upsert_mapping(track=track, store_path=store_path)
    return track
