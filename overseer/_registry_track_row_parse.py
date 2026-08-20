"""Smart constructors that parse loose mapping rows into typed track records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias, cast

from _registry_track_variants import (
    MISSING_EPIC,
    MISSING_SUPERVISED_TOPIC,
    MISSING_TMUX,
    ForemanSeat,
    GroomingSeat,
    ModelProfile,
    PlanTrack,
    SupervisorSeat,
    TrackRecord,
    UnassignedPlan,
    unresolved_plan_epic,
)
from _signals_topics import reserved_worker_suffix, topic_supervised_worker

__all__: list[str] = [
    "RowExtras",
    "optional_model_profile",
    "require_str",
    "track_from_mapping_row",
]


def require_str(*, row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or value == "":
        if key == "tmux":
            raise ValueError(MISSING_TMUX)
        if key == "epic":
            raise ValueError(MISSING_EPIC)
        raise ValueError(f"missing_{key}")
    return value


def optional_str(*, row: dict[str, object], key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) and value else None


def optional_model_profile(*, value: object) -> ModelProfile | None:
    if not isinstance(value, dict):
        return None
    profile = cast("dict[object, object]", value)
    if not all(
        isinstance(key, str) and (isinstance(item, str) or item is None)
        for key, item in profile.items()
    ):
        return None
    return cast("ModelProfile", profile)


@dataclass(frozen=True, kw_only=True)
class RowExtras:
    resume: str | None
    ctx_threshold: int | None
    pinned_session_id: str | None
    observed_session_identity: str | None
    added_at: str | None
    model_profile: ModelProfile | None


def _row_kind(*, row: dict[str, object], topic: str) -> str:
    kind = row.get("kind")
    if isinstance(kind, str) and kind:
        return kind
    suffix = reserved_worker_suffix(topic=topic)
    if suffix == "-supervisor":
        return "supervisor"
    if suffix == "-foreman":
        return "foreman"
    if suffix == "-grooming":
        return "grooming"
    return "plan"


def track_from_mapping_row(
    *,
    row: dict[str, object],
    extras: RowExtras,
) -> TrackRecord:
    topic = require_str(row=row, key="topic")
    repo = require_str(row=row, key="repo")
    kind = _row_kind(row=row, topic=topic)
    if kind == "plan":
        return PlanTrack(
            topic=topic,
            repo=repo,
            tmux=optional_str(row=row, key="tmux") or topic,
            epic=optional_str(row=row, key="epic") or unresolved_plan_epic(topic=topic),
            resume=extras.resume,
            ctx_threshold=extras.ctx_threshold,
            pinned_session_id=extras.pinned_session_id,
            observed_session_identity=extras.observed_session_identity,
            added_at=extras.added_at,
            model_profile=extras.model_profile,
        )
    if kind == "supervisor":
        tmux = require_str(row=row, key="tmux")
        epic = require_str(row=row, key="epic")
        supervised_topic = topic_supervised_worker(topic=topic)
        if supervised_topic is None:
            raise ValueError(MISSING_SUPERVISED_TOPIC)
        return SupervisorSeat(
            topic=topic,
            repo=repo,
            tmux=tmux,
            epic=epic,
            supervised_topic=supervised_topic,
            resume=extras.resume,
            ctx_threshold=extras.ctx_threshold,
            pinned_session_id=extras.pinned_session_id,
            observed_session_identity=extras.observed_session_identity,
            added_at=extras.added_at,
            model_profile=extras.model_profile,
        )
    if kind == "foreman":
        epic = (
            unresolved_plan_epic(topic=topic)
            if "epic" not in row or row.get("epic") is None
            else require_str(row=row, key="epic")
        )
        return ForemanSeat(
            topic=topic,
            repo=repo,
            tmux=require_str(row=row, key="tmux"),
            epic=epic,
            resume=extras.resume,
            ctx_threshold=extras.ctx_threshold,
            pinned_session_id=extras.pinned_session_id,
            observed_session_identity=extras.observed_session_identity,
            added_at=extras.added_at,
            model_profile=extras.model_profile,
        )
    if kind == "grooming":
        epic = (
            unresolved_plan_epic(topic=topic)
            if "epic" not in row or row.get("epic") is None
            else require_str(row=row, key="epic")
        )
        return GroomingSeat(
            topic=topic,
            repo=repo,
            tmux=require_str(row=row, key="tmux"),
            epic=epic,
            resume=extras.resume,
            ctx_threshold=extras.ctx_threshold,
            pinned_session_id=extras.pinned_session_id,
            observed_session_identity=extras.observed_session_identity,
            added_at=extras.added_at,
            model_profile=extras.model_profile,
        )
    raise ValueError(f"unknown_kind:{kind}")


if TYPE_CHECKING:
    Track: TypeAlias = TrackRecord
else:

    class Track:
        def __new__(cls, **kwargs: object) -> TrackRecord:
            del cls
            topic = require_str(row=kwargs, key="topic")
            repo = require_str(row=kwargs, key="repo")
            tmux = optional_str(row=kwargs, key="tmux")
            epic = optional_str(row=kwargs, key="epic")
            assigned = kwargs.get("assigned")
            if assigned is False:
                return UnassignedPlan.make(repo=repo, topic=topic)
            row: dict[str, object] = {"topic": topic, "repo": repo}
            if tmux is not None:
                row["tmux"] = tmux
            if epic is not None:
                row["epic"] = epic
            return track_from_mapping_row(
                row=row,
                extras=RowExtras(
                    resume=optional_str(row=kwargs, key="resume"),
                    ctx_threshold=(
                        kwargs.get("ctx_threshold")
                        if isinstance(kwargs.get("ctx_threshold"), int)
                        else None
                    ),
                    pinned_session_id=optional_str(row=kwargs, key="pinned_session_id"),
                    observed_session_identity=optional_str(
                        row=kwargs, key="observed_session_identity"
                    ),
                    added_at=optional_str(row=kwargs, key="added_at"),
                    model_profile=optional_model_profile(value=kwargs.get("model_profile")),
                ),
            )

        @staticmethod
        def make_unassigned(*, repo: str, topic: str) -> UnassignedPlan:
            return UnassignedPlan.make(repo=repo, topic=topic)
