"""Route durable pane coordinates to their recorded terminal instance."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import cast

import _herdr_shell_identity
import claude_sessions
import herdr_adapter
import herdr_initial_start
import herdr_replacement
import herdr_write
import pane_router_initial_start
import pane_router_ownership
import pane_router_read_facade
import pane_router_reads
import pane_router_replacement
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
_THIS_MODULE = sys.modules[__name__]
sys.modules["pane_router"] = _THIS_MODULE
sys.modules["overseer.pane_router"] = _THIS_MODULE


@dataclass(kw_only=True)
class MixedPaneDriver:
    """Resolve every qualified pane on its recorded backend and generation."""

    tmux: PaneDriver = field(default_factory=tmuxio.TmuxIO)
    herdr: pane_router_reads.HerdrObserver = field(default_factory=herdr_adapter.HerdrAdapter)
    herdr_writer: pane_router_replacement.ReplacementInput = field(
        default_factory=herdr_write.HerdrWriter
    )
    initial_start: herdr_initial_start.HerdrInitialStart = field(
        default_factory=lambda: herdr_initial_start.HerdrInitialStart(
            writer=herdr_write.HerdrWriter()
        )
    )
    replacement_process_of: herdr_replacement.ProcessReader = herdr_replacement.proc_process
    replacement_process_ids: herdr_replacement.ProcessIds = herdr_replacement.proc_process_ids
    replacement_terminator: herdr_replacement.GroupTerminator = (
        herdr_replacement.terminate_process_group
    )
    replacement_login_shells: frozenset[str] = field(
        default_factory=_herdr_shell_identity.system_login_shells
    )
    replacement_snapshots: dict[str, herdr_replacement.ReplacementSnapshot] = field(
        default_factory=dict
    )
    herdr_endpoints: Callable[[], Iterable[str]] = pane_router_ownership.default_herdr_endpoints
    tmux_run: tmux_process.TextProcessRun = tmux_process.TEXT_PROCESS_RUN
    coordinates: set[str] = field(default_factory=set)
    prompt_states: dict[str, pane_router_submit_signals.PromptState] = field(default_factory=dict)

    register_coordinates = pane_router_read_facade.register_coordinates
    capture_pane = pane_router_read_facade.capture_pane
    pane_id = pane_router_read_facade.pane_id
    pane_pid = pane_router_read_facade.pane_pid
    pane_current_command = pane_router_read_facade.pane_current_command
    pane_current_path = pane_router_read_facade.pane_current_path
    session_exists = pane_router_read_facade.session_exists
    pane_pid_sessions = pane_router_read_facade.pane_pid_sessions
    renumbered_herdr_coordinate = pane_router_read_facade.renumbered_herdr_coordinate
    pane_by_title = pane_router_read_facade.pane_by_title

    def _writes(self) -> pane_router_writes.PaneRoutingWrites:
        return pane_router_writes.PaneRoutingWrites(
            reads=pane_router_read_facade.reads(driver=self),
            herdr_writer=self.herdr_writer,
            prompt_states=self.prompt_states,
        )

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

    pending_initial_start = pane_router_initial_start.pending_initial_start
    create_initial_pane = pane_router_initial_start.create_initial_pane
    created_initial_pane_persisted = pane_router_initial_start.created_initial_pane_persisted
    launch_initial_agent = pane_router_initial_start.launch_initial_agent
    finish_initial_agent = pane_router_initial_start.finish_initial_agent
    preserve_initial_pane = pane_router_initial_start.preserve_initial_pane
    cleanup_initial_pane = pane_router_initial_start.preserve_initial_pane

    def _replacement(self) -> herdr_replacement.ReplacementController:
        return pane_router_replacement.controller(
            observer=self.herdr,
            writer=self.herdr_writer,
            process_of=self.replacement_process_of,
            process_ids=self.replacement_process_ids,
            terminate_group=self.replacement_terminator,
            login_shells=self.replacement_login_shells,
        )

    def herdr_replacement_snapshot(self, *, session: str) -> herdr_replacement.ReplacementSnapshot:
        snapshot = self._replacement().snapshot(
            target=pane_router_replacement.target(session=session)
        )
        self.replacement_snapshots[session] = snapshot
        return snapshot

    def herdr_terminate(
        self, *, session: str, process_group: int
    ) -> herdr_replacement.ReplacementOutcome:
        return self._replacement().terminate(
            target=pane_router_replacement.target(session=session),
            process_group=process_group,
            expected=self.replacement_snapshots.pop(session, None),
        )

    def herdr_launch(
        self,
        *,
        session: str,
        cwd: str,
        command: str,
        env: Mapping[str, str | None],
    ) -> herdr_replacement.ReplacementOutcome:
        return self._replacement().launch(
            target=pane_router_replacement.target(session=session),
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

    def retry_prompt_enter_once(
        self,
        *,
        session: str,
        text: str,
        sleep: Callable[[float], None],
    ) -> tuple[bool, bool]:
        return self._writes().retry_prompt_enter_once(
            session=session,
            text=text,
            sleep=sleep,
        )


def default_pane_driver() -> PaneDriver:
    return cast(PaneDriver, MixedPaneDriver())


def register_coordinates(*, driver: PaneDriver, coordinates: Iterable[str]) -> None:
    if isinstance(driver, MixedPaneDriver):
        driver.register_coordinates(coordinates=coordinates)


def current_process_coordinate() -> str | None:
    """Exact qualified owner of this process, proven by live ancestry."""
    return pane_router_ownership.current_process_coordinate(
        process_pid=PROCESS_PID,
        process_ppid=PROCESS_PPID,
        probes=OWNERSHIP_PROBES(),
    )
