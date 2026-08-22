"""Deterministic process wrapper for the per-repo foreman runtime."""
# livespec-lloc-soft-band-owner: overseer-lixhd3.1

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import registry
from _supervisor_foreman import heartbeat_lapse, heartbeat_path
from foreman_act_record import AppendJournal, append_journal
from foreman_runtime_autonomy import (
    STANDING_ORDERS_TEMPLATE,
    SeatComments,
    default_seat_comments,
    full_autonomy_report,
)
from foreman_runtime_backoff import (
    DEFAULT_MAX_LLM_TICK_INTERVAL_SECONDS,
    auto_resume_interval,
    effective_interval,
)
from foreman_runtime_document import (
    ForemanDocument,
    foreman_blocking_prompt_open,
    foreman_document,
)
from foreman_runtime_escalation import record_blocking_prompt_escalation
from foreman_runtime_identity import EntryGateResult, canonical_session_name, entry_gate
from foreman_runtime_lock import ForemanLock, LockResult
from foreman_runtime_policy import exit_reason, stable_ticks
from foreman_runtime_state import atomic_json, read_json_object, state_path

__all__: list[str] = [
    "DEFAULT_HARD_TICK_BUDGET",
    "DEFAULT_LLM_TICK_INTERVAL_SECONDS",
    "DEFAULT_MAX_LLM_TICK_INTERVAL_SECONDS",
    "DEFAULT_WATCH_INTERVAL_SECONDS",
    "STANDING_ORDERS_TEMPLATE",
    "EntryGateResult",
    "ForemanConfig",
    "ForemanDocument",
    "ForemanLock",
    "ForemanRuntime",
    "LockResult",
    "StepResult",
    "canonical_session_name",
    "entry_gate",
    "register_foreman_track",
]

DEFAULT_LLM_TICK_INTERVAL_SECONDS = 60.0 * 60.0
DEFAULT_WATCH_INTERVAL_SECONDS = 5.0 * 60.0
DEFAULT_HARD_TICK_BUDGET = 36


class _LlmTick(Protocol):
    def __call__(self, *, document: ForemanDocument) -> bool: ...


class _TimeSource(Protocol):
    def __call__(self) -> float: ...


@dataclass(frozen=True, kw_only=True)
class ForemanConfig:
    llm_tick_interval_seconds: float = DEFAULT_LLM_TICK_INTERVAL_SECONDS
    watch_interval_seconds: float = DEFAULT_WATCH_INTERVAL_SECONDS
    hard_tick_budget: int = DEFAULT_HARD_TICK_BUDGET
    converged_ticks: int = 2
    max_llm_tick_interval_seconds: float = DEFAULT_MAX_LLM_TICK_INTERVAL_SECONDS


@dataclass(frozen=True, kw_only=True)
class StepResult:
    tick_generation: int
    llm_tick: bool
    action_taken: bool
    exit_reason: str | None
    loop_lapsed: bool
    heartbeat_age_seconds: float | None
    blocking_prompt_open: bool
    tick_ended_with_blocking_prompt: bool
    llm_tick_interval_seconds: float
    auto_resume_interval_seconds: float | None
    full_autonomy: bool
    decision_rule: object
    conflict: bool
    attention_conditions: list[dict[str, str]]
    standing_orders: str | None
    standing_orders_recorded: bool | None
    full_autonomy_terminating_condition_reached: bool


def register_foreman_track(
    *,
    repo: str | os.PathLike[str],
    epic: str | None = None,
    store_path: str | os.PathLike[str] | None = None,
) -> registry.Track:
    repo_path = Path(repo).resolve()
    session_name = canonical_session_name(repo=repo_path)
    track = registry.ForemanSeat(
        topic=session_name,
        repo=str(repo_path),
        tmux=session_name,
        epic=epic or registry.unresolved_plan_epic(topic=session_name),
    )
    _ = registry.upsert_mapping(track=track, store_path=store_path)
    return track


def _default_llm_tick(*, document: ForemanDocument) -> bool:
    del document
    return False


class ForemanRuntime:
    def __init__(
        self,
        *,
        repo: str | os.PathLike[str],
        now: _TimeSource,
        config: ForemanConfig | None = None,
        llm_tick: _LlmTick = _default_llm_tick,
        append_journal: AppendJournal = append_journal,
        seat_comments: SeatComments = default_seat_comments,
    ) -> None:
        self.repo = Path(repo).resolve()
        self.now = now
        self.config = config if config is not None else ForemanConfig()
        self.llm_tick = llm_tick
        self.append_journal = append_journal
        self.seat_comments = seat_comments

    def _read_state(self) -> dict[str, object]:
        return read_json_object(path=state_path(repo=self.repo))

    def _write_state(self, *, state: dict[str, object]) -> None:
        atomic_json(path=state_path(repo=self.repo), payload=state)

    def _write_heartbeat(self, *, tick_generation: int, interval_seconds: float) -> None:
        written = datetime.fromtimestamp(self.now(), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        atomic_json(
            path=heartbeat_path(repo=str(self.repo)),
            payload={
                "written_at": written,
                "pid": os.getpid(),
                "tick_generation": tick_generation,
                "tick_interval_seconds": interval_seconds,
            },
        )

    def step(self, *, document: dict[str, object]) -> StepResult:
        state = self._read_state()
        interval_seconds = effective_interval(
            state=state, configured_seconds=self.config.llm_tick_interval_seconds
        )
        tick_generation = _int_state(value=state.get("tick_generation")) + 1
        # Read BEFORE _write_heartbeat() overwrites it below, so a lapsed recurring
        # loop (no tick landed for 2x its interval) is visible to THIS tick, not just
        # to the daemon's own next poll of the file this call is about to replace.
        lapse = heartbeat_lapse(repo=str(self.repo), now=self.now)
        doc = foreman_document(payload=document)
        scheduled_at = _float_state(value=state.get("next_llm_tick_at"))
        now = self.now()
        due = scheduled_at <= now
        action_taken = self.llm_tick(document=doc) if due else False
        stable_tick_count = stable_ticks(
            state=state,
            document=doc,
            action_taken=action_taken,
            scheduled_tick=due,
        )
        next_llm_tick_at = now + interval_seconds if due else scheduled_at
        reason = exit_reason(
            tick_generation=tick_generation,
            stable_ticks=stable_tick_count,
            document=doc,
            hard_tick_budget=self.config.hard_tick_budget,
            converged_ticks=self.config.converged_ticks,
        )
        auto_resume_interval_seconds = (
            auto_resume_interval(
                repo=self.repo,
                append_journal=self.append_journal,
                interval_seconds=interval_seconds,
                max_interval_seconds=self.config.max_llm_tick_interval_seconds,
                tick_generation=tick_generation,
            )
            if reason == "hard-tick-budget"
            else None
        )
        reported_generation = tick_generation
        if auto_resume_interval_seconds is not None:
            interval_seconds = auto_resume_interval_seconds
            next_llm_tick_at = now + interval_seconds
            tick_generation = 0
            stable_tick_count = 0
        self._write_state(
            state={
                "tick_generation": tick_generation,
                "next_llm_tick_at": next_llm_tick_at,
                "last_fingerprint": doc.fingerprint,
                "last_generation_fingerprint": doc.generation_fingerprint,
                "stable_ticks": stable_tick_count,
                "llm_tick_interval_seconds": interval_seconds,
            }
        )
        self._write_heartbeat(tick_generation=tick_generation, interval_seconds=interval_seconds)
        blocking_prompt_open = foreman_blocking_prompt_open(
            payload=document,
            foreman_topic=canonical_session_name(repo=self.repo),
        )
        if blocking_prompt_open:
            record_blocking_prompt_escalation(repo=self.repo)
        autonomy = full_autonomy_report(
            repo=self.repo,
            document=document,
            seat_comments=self.seat_comments,
        )
        return StepResult(
            tick_generation=reported_generation,
            llm_tick=due,
            action_taken=action_taken,
            exit_reason=reason,
            loop_lapsed=lapse.stale if lapse is not None else False,
            heartbeat_age_seconds=lapse.age_seconds if lapse is not None else None,
            blocking_prompt_open=blocking_prompt_open,
            tick_ended_with_blocking_prompt=blocking_prompt_open,
            llm_tick_interval_seconds=interval_seconds,
            auto_resume_interval_seconds=auto_resume_interval_seconds,
            full_autonomy=autonomy.full_autonomy,
            decision_rule=autonomy.decision_rule,
            conflict=autonomy.conflict,
            attention_conditions=autonomy.attention_conditions,
            standing_orders=autonomy.standing_orders,
            standing_orders_recorded=autonomy.standing_orders_recorded,
            full_autonomy_terminating_condition_reached=(
                autonomy.full_autonomy_terminating_condition_reached
            ),
        )

    def resume(self) -> None:
        state = self._read_state()
        state["tick_generation"] = 0
        state["next_llm_tick_at"] = 0.0
        state["stable_ticks"] = 0
        state["llm_tick_interval_seconds"] = self.config.llm_tick_interval_seconds
        self._write_state(state=state)

    def token_free_watch(self, *, document: dict[str, object]) -> bool:
        state = self._read_state()
        current = foreman_document(payload=document).generation_fingerprint
        if state.get("last_generation_fingerprint") == current:
            return False
        state["last_generation_fingerprint"] = current
        self._write_state(state=state)
        return True


def _int_state(*, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _float_state(*, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)
