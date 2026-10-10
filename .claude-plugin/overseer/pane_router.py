"""Route durable pane coordinates to their recorded terminal instance."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import cast

import claude_sessions
import herdr_adapter
import herdr_identity
import herdr_write
import pane_router_coordinates
import pane_router_reads
import pane_router_submit_signals
import pane_router_writes
import terminal_ownership
import terminal_probes
import tmux_process
import tmuxio
from tmuxio_protocols import PaneDriver

__all__: list[str] = [
    "OWNERSHIP_PROBES",
    "PROCESS_PID",
    "PROCESS_PPID",
    "MixedPaneDriver",
    "current_process_coordinate",
    "default_pane_driver",
    "register_coordinates",
]

PROCESS_PID: Callable[[], int] = os.getpid
PROCESS_PPID = claude_sessions.proc_ppid
OWNERSHIP_PROBES: Callable[[], tuple[terminal_ownership.TerminalProbe, ...]] = partial(
    tuple,
    (
        terminal_probes.TmuxOwnershipProbe(),
        terminal_probes.HerdrOwnershipProbe(),
    ),
)
_DEFAULT_HERDR_ENDPOINTS = tuple(filter(None, (os.environ.get(terminal_probes.HERDR_SOCKET_ENV),)))
_THIS_MODULE = sys.modules[__name__]
sys.modules["pane_router"] = _THIS_MODULE
sys.modules["overseer.pane_router"] = _THIS_MODULE


@dataclass(kw_only=True)
class MixedPaneDriver:
    """Resolve every qualified pane on its recorded backend and generation."""

    tmux: PaneDriver = field(default_factory=tmuxio.TmuxIO)
    herdr: pane_router_reads.HerdrObserver = field(default_factory=herdr_adapter.HerdrAdapter)
    herdr_writer: pane_router_submit_signals.HerdrInput = field(
        default_factory=herdr_write.HerdrWriter
    )
    herdr_endpoints: Callable[[], Iterable[str]] = field(
        default_factory=lambda: partial(tuple, _DEFAULT_HERDR_ENDPOINTS)
    )
    tmux_run: tmux_process.TextProcessRun = tmux_process.TEXT_PROCESS_RUN
    coordinates: set[str] = field(default_factory=set)
    prompt_states: dict[str, pane_router_submit_signals.PromptState] = field(default_factory=dict)

    def _reads(self) -> pane_router_reads.PaneRoutingReads:
        return pane_router_reads.PaneRoutingReads(
            tmux=self.tmux,
            herdr=self.herdr,
            herdr_endpoints=self.herdr_endpoints,
            tmux_run=self.tmux_run,
            coordinates=self.coordinates,
        )

    def register_coordinates(self, *, coordinates: Iterable[str]) -> None:
        self.coordinates.update(coordinates)

    def _writes(self) -> pane_router_writes.PaneRoutingWrites:
        return pane_router_writes.PaneRoutingWrites(
            reads=self._reads(),
            herdr_writer=self.herdr_writer,
            prompt_states=self.prompt_states,
        )

    def capture_pane(self, *, session: str) -> str:
        return self._reads().capture_pane(session=session)

    def pane_id(self, *, session: str) -> str | None:
        return self._reads().pane_id(session=session)

    def pane_pid(self, *, session: str) -> int | None:
        return self._reads().pane_pid(session=session)

    def pane_current_command(self, *, session: str) -> str | None:
        return self._reads().pane_current_command(session=session)

    def pane_current_path(self, *, session: str) -> str | None:
        return self._reads().pane_current_path(session=session)

    def session_exists(self, *, session: str) -> bool:
        return self._reads().session_exists(session=session)

    def pane_pid_sessions(self) -> dict[int, str]:
        return self._reads().pane_pid_sessions()

    def pane_by_title(self, *, pane: str, title: str) -> str | None:
        decoded = self._reads().decode(value=pane)
        if decoded.herdr is not None or decoded.tmux is not None or decoded.error:
            return None
        return self.tmux.pane_by_title(pane=pane, title=title)

    def send_keys(self, *, session: str, keys: str) -> bool:
        return self._writes().send_keys(session=session, keys=keys)

    def bracketed_paste(self, *, session: str, text: str) -> bool:
        return self._writes().bracketed_paste(session=session, text=text)

    def respawn_pane(
        self,
        *,
        session: str,
        cwd: str,
        command: str,
        env: Mapping[str, str | None] | None = None,
    ) -> bool:
        return self._writes().respawn_pane(
            session=session,
            cwd=cwd,
            command=command,
            env=env,
        )

    def new_session(self, *, name: str, cwd: str) -> bool:
        return self._writes().new_session(name=name, cwd=cwd)

    def kill_session(self, *, session: str) -> bool:
        return self._writes().kill_session(session=session)

    def rename_window(self, *, pane: str, name: str) -> bool:
        return self._writes().rename_window(pane=pane, name=name)

    def submit_prompt_once(
        self,
        *,
        session: str,
        text: str,
        expect_codex: bool,
        sleep: Callable[[float], None],
    ) -> tuple[bool, bool]:
        return self._writes().submit_prompt_once(
            session=session,
            text=text,
            expect_codex=expect_codex,
            sleep=sleep,
        )


def default_pane_driver() -> PaneDriver:
    return cast(PaneDriver, MixedPaneDriver())


def register_coordinates(*, driver: PaneDriver, coordinates: Iterable[str]) -> None:
    if isinstance(driver, MixedPaneDriver):
        driver.register_coordinates(coordinates=coordinates)


def current_process_coordinate() -> str | None:
    """Exact qualified owner of this process, proven by live ancestry."""
    selected = terminal_ownership.select_owner(
        pid=PROCESS_PID(),
        environ=dict(os.environ),
        probes=OWNERSHIP_PROBES(),
        ppid_of=PROCESS_PPID,
    )
    claim = selected.claim
    renderers: dict[str, Callable[[], str | None]] = {
        herdr_identity.HERDR_BACKEND: lambda: pane_router_coordinates.qualified_coordinate(
            claim=cast(terminal_ownership.OwnershipClaim, claim)
        ),
        herdr_identity.TMUX_BACKEND: lambda: pane_router_coordinates.qualified_coordinate(
            claim=cast(terminal_ownership.OwnershipClaim, claim)
        ),
    }
    return renderers.get(getattr(claim, "backend", ""), lambda: None)()
