"""Context and seam types a caam decision pass is parameterised by."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from caam_anthropic_finish import LineWriter, SaveState
from caam_decision import UsageRecord
from caam_switch import SwitchRequest, SwitchResult

__all__: list[str] = [
    "DecisionContext",
    "DecisionSeams",
    "Flags",
    "SwitchAccount",
    "UsageFetcher",
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
