"""Revive dark caam profile rows on demand before rotation gives up."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import jsonio
from caam_decision import ProfileUsage, UsageRecord
from caam_profile_state import caam_vault
from caam_warm import AgentRunner, Logger, warm_profile

__all__: list[str] = [
    "ReviveContext",
    "RevivePassContext",
    "RevivePassSeams",
    "UsageFetcher",
    "revive_dark_profiles",
    "revive_pass_profiles",
]


class UsageFetcher(Protocol):
    def __call__(
        self,
        *,
        creds_path: Path,
        now: float | None = None,
    ) -> tuple[UsageRecord | None, str | None]: ...


class LineWriter(Protocol):
    def __call__(self, line: str) -> None: ...


class RevivePassContext(Protocol):
    @property
    def state(self) -> dict[str, object]: ...

    @property
    def home(self) -> Path: ...

    @property
    def now(self) -> float: ...

    @property
    def stdout(self) -> LineWriter: ...


class RevivePassSeams(Protocol):
    @property
    def fetcher(self) -> UsageFetcher: ...

    @property
    def agent_runner(self) -> AgentRunner: ...


@dataclass(frozen=True, kw_only=True)
class ReviveContext:
    active_name: str
    state: dict[str, object]
    home: Path
    now: float
    fetcher: UsageFetcher
    agent_runner: AgentRunner
    logger: Logger


def revive_pass_profiles(
    *,
    active_name: str,
    context: RevivePassContext,
    profiles: tuple[ProfileUsage, ...],
    seams: RevivePassSeams,
) -> tuple[ProfileUsage, ...]:
    return revive_dark_profiles(
        context=ReviveContext(
            active_name=active_name,
            state=context.state,
            home=context.home,
            now=context.now,
            fetcher=seams.fetcher,
            agent_runner=seams.agent_runner,
            logger=_LineLogger(writer=context.stdout),
        ),
        profiles=profiles,
    )


def revive_dark_profiles(
    *,
    context: ReviveContext,
    profiles: tuple[ProfileUsage, ...],
) -> tuple[ProfileUsage, ...]:
    """Attempt one sandbox refresh for rows that are already dark."""

    return tuple(_revive_dark_profile(context=context, profile=profile) for profile in profiles)


def _revive_dark_profile(*, context: ReviveContext, profile: ProfileUsage) -> ProfileUsage:
    snapshot = caam_vault(home=context.home) / profile.name / ".credentials.json"
    if _should_revive(context=context, profile=profile, snapshot=snapshot):
        result = warm_profile(
            name=profile.name,
            home=context.home,
            now=context.now,
            agent_runner=context.agent_runner,
            logger=context.logger,
        )
        context.logger(f"revive: {profile.name} {result.detail}")
        if result.ok:
            usage, _ = context.fetcher(creds_path=snapshot, now=context.now)
            if usage is not None:
                _cache_profile(state=context.state, name=profile.name, usage=usage, now=context.now)
                return ProfileUsage(name=profile.name, source="live", usage=usage)
    return profile


def _should_revive(*, context: ReviveContext, profile: ProfileUsage, snapshot: Path) -> bool:
    return (
        profile.name != context.active_name
        and snapshot.exists()
        and (
            profile.credential_expired
            or (profile.usage is None and profile.source.startswith("dark: "))
        )
    )


def _cache_profile(*, state: dict[str, object], name: str, usage: UsageRecord, now: float) -> None:
    profiles_value = jsonio.as_object(value=state.get("profiles"))
    profiles = {} if profiles_value is None else profiles_value
    state["profiles"] = profiles
    profiles[name] = {
        "at": now,
        "five_hour_remaining": usage.five_hour_remaining,
        "seven_day_remaining": usage.seven_day_remaining,
        "five_hour_resets_at": usage.five_hour_resets_at,
        "seven_day_resets_at": usage.seven_day_resets_at,
        "fable_remaining": usage.fable_remaining,
        "fable_resets_at": usage.fable_resets_at,
    }


@dataclass(frozen=True, kw_only=True)
class _LineLogger:
    writer: LineWriter

    def __call__(self, message: str) -> None:
        self.writer(message)
