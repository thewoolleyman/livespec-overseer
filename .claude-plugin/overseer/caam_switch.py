"""Serialized switch execution for caam account rotation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Protocol, cast

from _caam_switch_host import (
    SwitchLock,
    SwitchLockFactory,
    acquire_switch_lock,
    caam_activate,
)
from caam_decision import ProfileUsage, UsageRecord, decision_switched
from caam_profile_state import caam_vault, live_creds_path
from caam_usage import read_creds

__all__: list[str] = [
    "ACTIVATE_TIMEOUT_S",
    "LOCK_REL",
    "ActivateRunner",
    "ActiveReader",
    "CaamProcess",
    "SaveState",
    "SwitchLock",
    "SwitchLockFactory",
    "SwitchRequest",
    "SwitchResult",
    "UsageFetcher",
    "acquire_switch_lock",
    "caam_activate",
    "switch_account",
]

ACTIVATE_TIMEOUT_S: Final = 60.0
LOCK_REL: Final = Path(".local/state/caam-usage-rotate/switch.lock")
_TOOL: Final = "claude"
_HOLD_LOCKED: Final = "hold: another caam-anthropic-loop holds the switch lock"


class CaamProcess(Protocol):
    returncode: int
    stdout: str
    stderr: str


class ActivateRunner(Protocol):
    def __call__(self, *, args: tuple[str, ...], timeout: float) -> CaamProcess: ...


class ActiveReader(Protocol):
    def __call__(self) -> str | None: ...


class SaveState(Protocol):
    def __call__(self, *, state: dict[str, object]) -> None: ...


class UsageFetcher(Protocol):
    def __call__(
        self,
        *,
        creds_path: Path,
        now: float | None = None,
    ) -> tuple[UsageRecord | None, str | None]: ...


@dataclass(frozen=True, kw_only=True)
class SwitchResult:
    exit_code: int
    lines: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class SwitchRequest:
    active_name: str
    target: ProfileUsage
    current: UsageRecord
    state: dict[str, object]
    home: Path
    now: float
    active_reader: ActiveReader
    fetcher: UsageFetcher
    activator: ActivateRunner
    lock_factory: SwitchLockFactory
    save: SaveState


def switch_account(*, request: SwitchRequest) -> SwitchResult:
    try:
        return _switch_account_uncaught(request=request)
    except (OSError, RuntimeError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        request.save(state=request.state)
        return SwitchResult(exit_code=2, lines=(f"FAIL {type(exc).__name__}: {exc}",))


def _switch_account_uncaught(*, request: SwitchRequest) -> SwitchResult:
    lock = request.lock_factory(lock_path=request.home / LOCK_REL)
    if lock is None:
        request.save(state=request.state)
        return SwitchResult(exit_code=0, lines=(_HOLD_LOCKED,))

    with lock:
        active_under_lock = request.active_reader()
        if active_under_lock != request.active_name:
            request.save(state=request.state)
            return SwitchResult(
                exit_code=0,
                lines=(
                    "hold: active changed "
                    f"{request.active_name} -> {active_under_lock} while deciding; "
                    "re-evaluating next tick",
                ),
            )

        usage, why = request.fetcher(
            creds_path=caam_vault(home=request.home) / request.target.name / ".credentials.json",
            now=request.now,
        )
        if usage is None:
            request.save(state=request.state)
            return SwitchResult(
                exit_code=2,
                lines=(
                    "FAIL refusing to switch to "
                    f"{request.target.name} -- its stored credential does not work right now "
                    f"({why}). Installing it would break every running session.",
                ),
            )

        process = request.activator(
            args=("activate", _TOOL, request.target.name),
            timeout=ACTIVATE_TIMEOUT_S,
        )
        if process.returncode != 0:
            request.save(state=request.state)
            return SwitchResult(
                exit_code=2,
                lines=(
                    f"FAIL caam activate {request.target.name}: "
                    f"{_process_message(process=process)}",
                ),
            )

    if _switch_did_not_stick(home=request.home, target_name=request.target.name):
        request.save(state=request.state)
        return SwitchResult(
            exit_code=2,
            lines=(
                "FAIL switch to "
                f"{request.target.name} did not stick -- the live credential no longer matches "
                "the snapshot. A running Claude session most likely refreshed its own token "
                "over the swap. Re-run to retry.",
            ),
        )

    request.state["last_switch"] = {
        "at": request.now,
        "from": request.active_name,
        "to": request.target.name,
    }
    request.save(state=request.state)
    return SwitchResult(
        exit_code=0,
        lines=(
            decision_switched(
                active_name=request.active_name,
                current_five_hour_used=request.current.five_hour,
                target=_target_summary(target=request.target, now=request.now),
            ),
        ),
    )


def _process_message(*, process: CaamProcess) -> str:
    message = process.stderr.strip() or process.stdout.strip()
    return message


def _switch_did_not_stick(*, home: Path, target_name: str) -> bool:
    target_token, _ = read_creds(
        path=caam_vault(home=home) / target_name / ".credentials.json",
    )
    live, _ = read_creds(path=live_creds_path(home=home))
    return target_token is not None and live is not None and target_token != live


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
