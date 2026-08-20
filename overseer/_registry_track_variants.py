"""Typed track records and smart constructors for mapping-store rows."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Literal, TypeAlias, overload

__all__: list[str] = [
    "LEGACY_UNRESOLVED_EPIC_PREFIX",
    "ForemanSeat",
    "ModelProfile",
    "PlanTrack",
    "SupervisorSeat",
    "TrackRecord",
    "UnassignedPlan",
    "epic_is_resolved",
    "track_with_epic",
    "unresolved_plan_epic",
]

ModelProfile: TypeAlias = dict[str, str | None]
TrackKind: TypeAlias = Literal["unassigned_plan", "plan", "supervisor", "foreman"]
LEGACY_UNRESOLVED_EPIC_PREFIX = "legacy-unresolved:"
MISSING_TMUX = "missing_tmux"
MISSING_EPIC = "missing_epic"
MISSING_SUPERVISED_TOPIC = "missing_supervised_topic"
PLAN_REQUIRES_TMUX = "plan track requires tmux"
PLAN_REQUIRES_EPIC = "plan track requires epic"
SUPERVISOR_REQUIRES_TMUX = "supervisor seat requires tmux"
SUPERVISOR_REQUIRES_EPIC = "supervisor seat requires epic"
SUPERVISOR_REQUIRES_TOPIC = "supervisor seat requires supervised topic"
FOREMAN_REQUIRES_TMUX = "foreman seat requires tmux"
FOREMAN_REQUIRES_EPIC = "foreman seat requires epic"


def unresolved_plan_epic(*, topic: str) -> str:
    return f"{LEGACY_UNRESOLVED_EPIC_PREFIX}{topic}"


def epic_is_resolved(*, epic: str | None) -> bool:
    return epic is not None and not epic.startswith(LEGACY_UNRESOLVED_EPIC_PREFIX)


@dataclass(frozen=True, kw_only=True)
class UnassignedPlan:
    topic: str
    repo: str
    kind: Literal["unassigned_plan"] = field(default="unassigned_plan", init=False)

    @property
    def assigned(self) -> bool:
        return False

    @property
    def is_unassigned(self) -> bool:
        return True

    @property
    def tmux(self) -> None:
        return None

    @property
    def resume(self) -> None:
        return None

    @property
    def epic(self) -> None:
        return None

    @property
    def ctx_threshold(self) -> None:
        return None

    @property
    def pinned_session_id(self) -> None:
        return None

    @property
    def observed_session_identity(self) -> None:
        return None

    @property
    def added_at(self) -> None:
        return None

    @property
    def model_profile(self) -> None:
        return None

    @classmethod
    def make(cls, *, repo: str, topic: str) -> UnassignedPlan:
        return cls(repo=repo, topic=topic)


@dataclass(frozen=True, kw_only=True)
class PlanTrack:
    topic: str
    repo: str
    tmux: str
    epic: str
    resume: str | None = None
    ctx_threshold: int | None = None
    pinned_session_id: str | None = None
    observed_session_identity: str | None = None
    added_at: str | None = None
    model_profile: ModelProfile | None = None
    kind: Literal["plan"] = field(default="plan", init=False)

    def __post_init__(self) -> None:
        if not self.tmux:
            raise ValueError(PLAN_REQUIRES_TMUX)
        if not self.epic:
            raise ValueError(PLAN_REQUIRES_EPIC)

    @property
    def assigned(self) -> bool:
        return True

    @property
    def is_unassigned(self) -> bool:
        return False


@dataclass(frozen=True, kw_only=True)
class SupervisorSeat:
    topic: str
    repo: str
    tmux: str
    epic: str
    supervised_topic: str
    resume: str | None = None
    ctx_threshold: int | None = None
    pinned_session_id: str | None = None
    observed_session_identity: str | None = None
    added_at: str | None = None
    model_profile: ModelProfile | None = None
    kind: Literal["supervisor"] = field(default="supervisor", init=False)

    def __post_init__(self) -> None:
        if not self.tmux:
            raise ValueError(SUPERVISOR_REQUIRES_TMUX)
        if not self.epic:
            raise ValueError(SUPERVISOR_REQUIRES_EPIC)
        if not self.supervised_topic:
            raise ValueError(SUPERVISOR_REQUIRES_TOPIC)

    @property
    def assigned(self) -> bool:
        return True

    @property
    def is_unassigned(self) -> bool:
        return False


@dataclass(frozen=True, kw_only=True)
class ForemanSeat:
    topic: str
    repo: str
    tmux: str
    epic: str
    resume: str | None = None
    ctx_threshold: int | None = None
    pinned_session_id: str | None = None
    observed_session_identity: str | None = None
    added_at: str | None = None
    model_profile: ModelProfile | None = None
    kind: Literal["foreman"] = field(default="foreman", init=False)

    def __post_init__(self) -> None:
        if not self.tmux:
            raise ValueError(FOREMAN_REQUIRES_TMUX)
        if not self.epic:
            raise ValueError(FOREMAN_REQUIRES_EPIC)

    @property
    def assigned(self) -> bool:
        return True

    @property
    def is_unassigned(self) -> bool:
        return False


TrackRecord: TypeAlias = UnassignedPlan | PlanTrack | SupervisorSeat | ForemanSeat


@overload
def track_with_epic(*, track: UnassignedPlan, epic: str) -> UnassignedPlan: ...


@overload
def track_with_epic(*, track: PlanTrack, epic: str) -> PlanTrack: ...


@overload
def track_with_epic(*, track: SupervisorSeat, epic: str) -> SupervisorSeat: ...


@overload
def track_with_epic(*, track: ForemanSeat, epic: str) -> ForemanSeat: ...


def track_with_epic(*, track: TrackRecord, epic: str) -> TrackRecord:
    if isinstance(track, UnassignedPlan):
        return track
    return dataclasses.replace(track, epic=epic)
