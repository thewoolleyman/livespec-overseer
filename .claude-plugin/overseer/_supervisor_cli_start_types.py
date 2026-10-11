"""Typed boundaries shared by deliberate-start orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import registry
from tmuxio_protocols import PaneDriver

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "NativeCleaner",
    "NativeCreator",
    "NativeMutation",
    "StartContext",
    "SupervisorFactory",
    "TmuxDeriver",
    "TmuxFactory",
]


class NativeMutation(Protocol):
    ok: bool
    target: str
    error: str
    effect_unknown: bool


class TmuxDeriver(Protocol):
    def __call__(self, *, repo: str, topic: str, allow_reserved: bool = False) -> str | None: ...


class TmuxFactory(Protocol):
    def __call__(self) -> PaneDriver: ...


class SupervisorFactory(Protocol):
    def __call__(self, *, tmux: PaneDriver) -> Supervisor: ...


class NativeCreator(Protocol):
    def create_initial_pane(self, *, source: str, name: str, cwd: str) -> NativeMutation: ...


class NativeCleaner(Protocol):
    def cleanup_initial_pane(self, *, session: str) -> bool: ...


@dataclass(frozen=True, kw_only=True)
class StartContext:
    io: PaneDriver
    sup: Supervisor
    track: registry.Track
    session: str
    native_source: str | None
    needs_native_creation: bool
    created_session: bool = False
