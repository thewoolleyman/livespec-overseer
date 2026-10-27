"""Dependency contracts used by the pure caam switch coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from _caam_switch_host import SwitchLockFactory
from caam_decision import ProfileUsage, UsageRecord

__all__: list[str] = [
    "ACTIVATE_TIMEOUT_S",
    "REASON_FAIL_ACTIVATE",
    "REASON_FAIL_DID_NOT_STICK",
    "REASON_FAIL_ERROR",
    "REASON_FAIL_POST_INSTALL_WRITE",
    "REASON_FAIL_RESTORE",
    "REASON_FAIL_STATE_VALIDATION",
    "REASON_FAIL_TARGET_CREDENTIAL",
    "REASON_HOLD_ACTIVE_CHANGED",
    "REASON_SWITCHED",
    "ActivateRunner",
    "ActiveReader",
    "CaamProcess",
    "SaveState",
    "SwitchRequest",
    "SwitchResult",
    "UsageFetcher",
]

ACTIVATE_TIMEOUT_S: Final = 60.0
REASON_SWITCHED: Final = "switched"
REASON_HOLD_ACTIVE_CHANGED: Final = "hold-active-changed"
REASON_FAIL_TARGET_CREDENTIAL: Final = "fail-target-credential"
REASON_FAIL_ACTIVATE: Final = "fail-activate"
REASON_FAIL_DID_NOT_STICK: Final = "fail-did-not-stick"
REASON_FAIL_ERROR: Final = "fail-error"
REASON_FAIL_POST_INSTALL_WRITE: Final = "fail-post-install-write"
REASON_FAIL_RESTORE: Final = "fail-restore"
REASON_FAIL_STATE_VALIDATION: Final = "fail-state-validation"


@dataclass(frozen=True, kw_only=True)
class SwitchResult:
    """The outcome of one serialized account switch attempt."""

    exit_code: int
    lines: tuple[str, ...]
    reason: str
    switched: bool = False


@dataclass(frozen=True, kw_only=True)
class SwitchRequest:
    """The injected inputs required to make one account switch decision."""

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
