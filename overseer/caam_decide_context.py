"""Context and seam types a caam decision pass is parameterised by."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from _caam_rotation_span import RotationSink
from caam_anthropic_finish import LineWriter, SaveState
from caam_decision import UsageRecord
from caam_switch import SwitchRequest, SwitchResult

__all__: list[str] = [
    "AfterSwitch",
    "DecisionContext",
    "DecisionSeams",
    "Flags",
    "LockContended",
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


class AfterSwitch(Protocol):
    """Called once, with the new active account, after a switch has succeeded.

    The decision path knows a switch happened; only the pass above it holds the
    polled profiles a table is drawn from. This seam carries the fact upward
    rather than moving the rendering down, and it is never called on a hold.
    """

    def __call__(self, *, active_name: str) -> None: ...


class LockContended(Protocol):
    """Called once when a switch attempt could not take the decision lock.

    A NEUTRAL FACT carried upward, not an interpretation: the pass above decides
    what a contended lock means for it. Today it means the pass must not publish
    its selected account -- spec.md v049 gives that write to the caller holding
    the lock, which is deciding the very fact the record would state -- but the
    decision path has no business knowing that, and a seam named for the
    consequence would have to be renamed by the next consequence.
    """

    def __call__(self) -> None: ...


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
    after_switch: AfterSwitch | None = None
    # Absent for every caller with nothing riding on the lock. A `decide` caller
    # that publishes nothing has nothing to forfeit when another caller is
    # already deciding, so it reports the contention to no one.
    lock_contended: LockContended | None = None
    # Where a `caam.rotation.switch` record goes. Absent for every caller that is
    # not a span-carrying rotation pass -- a direct `decide` caller has no trace to
    # hang one from, and reports nothing rather than emitting an orphan record.
    emit_rotation: RotationSink | None = None
