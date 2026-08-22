"""Account decision and switch execution for caam account rotation."""
# livespec-lloc-soft-band-owner: overseer-54k2za.23

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, cast

from _caam_switch_host import acquire_switch_lock, caam_activate
from caam_anthropic_finish import LineWriter, SaveState, finish
from caam_decision import (
    ProfileUsage,
    UsageRecord,
    binding,
    decision_dry_run,
    decision_forced,
    decision_hold_allowance,
    decision_hold_no_candidate,
    decision_trigger,
    eligible_profiles,
    five_hour_threshold,
    min_headroom_gain,
    rank_profiles,
    triggered,
    weekly_left,
    weekly_reserve,
)
from caam_profile_state import caam_vault
from caam_profiles import active_profile
from caam_switch import SwitchRequest, SwitchResult

__all__: list[str] = [
    "DecisionContext",
    "DecisionSeams",
    "Flags",
    "SwitchAccount",
    "UsageFetcher",
    "decide",
]


class Flags(Protocol):
    @property
    def force(self) -> bool: ...

    @property
    def dry_run(self) -> bool: ...


class UsageFetcher(Protocol):
    def __call__(
        self,
        *,
        creds_path: Path,
        now: float | None = None,
    ) -> tuple[UsageRecord | None, str | None]: ...


class SwitchAccount(Protocol):
    def __call__(self, *, request: SwitchRequest) -> SwitchResult: ...


class DecisionContext(Protocol):
    @property
    def flags(self) -> Flags: ...

    @property
    def home(self) -> Path: ...

    @property
    def now(self) -> float: ...

    @property
    def state(self) -> dict[str, object]: ...

    @property
    def state_path(self) -> Path: ...

    @property
    def stdout(self) -> LineWriter: ...


@dataclass(frozen=True, kw_only=True)
class DecisionSeams:
    fetcher: UsageFetcher
    save_state: SaveState
    switch_account: SwitchAccount


def decide(
    *,
    context: DecisionContext,
    profiles: tuple[ProfileUsage, ...],
    active_name: str,
    current: UsageRecord,
    seams: DecisionSeams,
) -> int:
    dimension, spent, label = binding(usage=current)
    if not context.flags.force and not triggered(usage=current):
        return _hold_allowed(
            context=context,
            save_state=seams.save_state,
            label=label,
            spent=spent,
            current=current,
        )
    decision_line = _trigger_line(
        flags=context.flags,
        label=label,
        spent=spent,
        current=current,
        dimension=dimension,
    )
    ranked = rank_profiles(
        profiles=eligible_profiles(
            profiles=profiles,
            active_name=active_name,
            current=current,
            force=context.flags.force,
            dimension=dimension,
        ).profiles
    )
    if not ranked:
        return _hold_no_candidate(
            context=context,
            save_state=seams.save_state,
            decision_line=decision_line,
            dimension=dimension,
            active_name=active_name,
        )
    if context.flags.dry_run:
        return _dry_run(
            context=context,
            save_state=seams.save_state,
            decision_line=decision_line,
            active_name=active_name,
            target=ranked[0],
        )
    return _switch_decision(
        context=context,
        active_name=active_name,
        current=current,
        target=ranked[0],
        decision_line=decision_line,
        seams=seams,
    )


def _hold_allowed(
    *,
    context: DecisionContext,
    save_state: SaveState,
    label: str,
    spent: float,
    current: UsageRecord,
) -> int:
    line = decision_hold_allowance(
        label=label,
        spent=spent,
        weekly_remaining=weekly_left(usage=current),
        reserve=weekly_reserve(),
    )
    return finish(
        code=0,
        state=context.state,
        state_path=context.state_path,
        save=save_state,
        stdout=context.stdout,
        lines=(line,),
    )


def _hold_no_candidate(
    *,
    context: DecisionContext,
    save_state: SaveState,
    decision_line: str,
    dimension: str,
    active_name: str,
) -> int:
    line = decision_hold_no_candidate(
        gain_needed=0.01 if context.flags.force else min_headroom_gain(),
        dimension=dimension,
        active_name=active_name,
    )
    return finish(
        code=0,
        state=context.state,
        state_path=context.state_path,
        save=save_state,
        stdout=context.stdout,
        lines=(decision_line, line),
    )


def _dry_run(
    *,
    context: DecisionContext,
    save_state: SaveState,
    decision_line: str,
    active_name: str,
    target: ProfileUsage,
) -> int:
    line = decision_dry_run(
        active_name=active_name,
        target=_target_summary(target=target, now=context.now),
    )
    return finish(
        code=0,
        state=context.state,
        state_path=context.state_path,
        save=save_state,
        stdout=context.stdout,
        lines=(decision_line, line),
    )


def _switch_decision(
    *,
    context: DecisionContext,
    active_name: str,
    current: UsageRecord,
    target: ProfileUsage,
    decision_line: str,
    seams: DecisionSeams,
) -> int:
    def save(*, state: dict[str, object]) -> None:
        seams.save_state(state=state, state_path=context.state_path)

    save(state=context.state)
    result = seams.switch_account(
        request=SwitchRequest(
            active_name=active_name,
            target=target,
            current=current,
            state=context.state,
            home=context.home,
            now=context.now,
            active_reader=lambda: active_profile(
                live_account_path=context.home / ".claude.json",
                vault_path=caam_vault(home=context.home),
                caam_runner=_run_caam,
            ),
            fetcher=seams.fetcher,
            activator=caam_activate,
            lock_factory=acquire_switch_lock,
            save=save,
        )
    )
    for line in (decision_line, *result.lines):
        context.stdout(line)
    return result.exit_code


def _trigger_line(
    *, flags: Flags, label: str, spent: float, current: UsageRecord, dimension: str
) -> str:
    if flags.force:
        return decision_forced(threshold=five_hour_threshold())
    return decision_trigger(
        label=label,
        spent=spent,
        weekly_remaining=weekly_left(usage=current),
        dimension=dimension,
    )


def _target_summary(*, target: ProfileUsage, now: float):
    from caam_rendering import SwitchTargetSummary

    usage = cast(UsageRecord, target.usage)
    return SwitchTargetSummary(
        name=target.name,
        weekly_used=usage.seven_day,
        weekly_reset=usage.seven_day_resets_at,
        source=target.source,
        now=datetime.fromtimestamp(now, tz=timezone.utc),
    )


def _run_caam(*, args: tuple[str, ...]):
    return caam_activate(args=args, timeout=60.0)
