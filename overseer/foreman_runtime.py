"""Deterministic process wrapper for the per-repo foreman runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from _supervisor_foreman import heartbeat_lapse, heartbeat_path
from foreman_runtime_document import ForemanDocument, foreman_document
from foreman_runtime_identity import EntryGateResult, canonical_session_name, entry_gate
from foreman_runtime_lock import ForemanLock, LockResult
from foreman_runtime_state import atomic_json, read_json_object, state_path

__all__: list[str] = [
    "DEFAULT_HARD_TICK_BUDGET",
    "DEFAULT_LLM_TICK_INTERVAL_SECONDS",
    "DEFAULT_WATCH_INTERVAL_SECONDS",
    "EntryGateResult",
    "ForemanConfig",
    "ForemanDocument",
    "ForemanLock",
    "ForemanRuntime",
    "LockResult",
    "StepResult",
    "canonical_session_name",
    "entry_gate",
]

DEFAULT_LLM_TICK_INTERVAL_SECONDS = 60.0 * 60.0
DEFAULT_WATCH_INTERVAL_SECONDS = 5.0 * 60.0
DEFAULT_HARD_TICK_BUDGET = 12


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


@dataclass(frozen=True, kw_only=True)
class StepResult:
    tick_generation: int
    llm_tick: bool
    action_taken: bool
    exit_reason: str | None
    loop_lapsed: bool
    heartbeat_age_seconds: float | None


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
    ) -> None:
        self.repo = Path(repo).resolve()
        self.now = now
        self.config = config if config is not None else ForemanConfig()
        self.llm_tick = llm_tick

    def _read_state(self) -> dict[str, object]:
        return read_json_object(path=state_path(repo=self.repo))

    def _write_state(self, *, state: dict[str, object]) -> None:
        atomic_json(path=state_path(repo=self.repo), payload=state)

    def _write_heartbeat(self, *, tick_generation: int) -> None:
        written = datetime.fromtimestamp(self.now(), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        atomic_json(
            path=heartbeat_path(repo=str(self.repo)),
            payload={
                "written_at": written,
                "pid": os.getpid(),
                "tick_generation": tick_generation,
                "tick_interval_seconds": self.config.llm_tick_interval_seconds,
            },
        )

    def step(self, *, document: dict[str, object]) -> StepResult:
        state = self._read_state()
        tick_generation = _int_state(value=state.get("tick_generation")) + 1
        # Read BEFORE _write_heartbeat() overwrites it below, so a lapsed recurring
        # loop (no tick landed for 2x its interval) is visible to THIS tick, not just
        # to the daemon's own next poll of the file this call is about to replace.
        lapse = heartbeat_lapse(repo=str(self.repo), now=self.now)
        doc = foreman_document(payload=document)
        due = _float_state(value=state.get("next_llm_tick_at")) <= self.now()
        action_taken = self.llm_tick(document=doc) if due else False
        stable_ticks = self._stable_ticks(
            state=state,
            document=doc,
            action_taken=action_taken,
            scheduled_tick=due,
        )
        self._write_state(
            state={
                "tick_generation": tick_generation,
                "next_llm_tick_at": self.now() + self.config.llm_tick_interval_seconds,
                "last_fingerprint": doc.fingerprint,
                "last_generation_fingerprint": doc.generation_fingerprint,
                "stable_ticks": stable_ticks,
            }
        )
        self._write_heartbeat(tick_generation=tick_generation)
        return StepResult(
            tick_generation=tick_generation,
            llm_tick=due,
            action_taken=action_taken,
            exit_reason=self._exit_reason(
                tick_generation=tick_generation, stable_ticks=stable_ticks, document=doc
            ),
            loop_lapsed=lapse.stale if lapse is not None else False,
            heartbeat_age_seconds=lapse.age_seconds if lapse is not None else None,
        )

    def _stable_ticks(
        self,
        *,
        state: dict[str, object],
        document: ForemanDocument,
        action_taken: bool,
        scheduled_tick: bool,
    ) -> int:
        if not document.monitored_entities or action_taken:
            return 0
        if state.get("last_fingerprint") != document.fingerprint:
            return 1 if scheduled_tick else 0
        if not scheduled_tick:
            return _int_state(value=state.get("stable_ticks"))
        return _int_state(value=state.get("stable_ticks")) + 1

    def _exit_reason(
        self, *, tick_generation: int, stable_ticks: int, document: ForemanDocument
    ) -> str | None:
        if tick_generation >= self.config.hard_tick_budget:
            return "hard-tick-budget"
        if document.monitored_entities and stable_ticks >= self.config.converged_ticks:
            return "converged"
        return None

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
