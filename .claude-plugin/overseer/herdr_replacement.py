"""Native Herdr process observation, one-shot termination, and retained-shell launch."""

from __future__ import annotations

import os
import signal
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import _herdr_shell_identity
import herdr_adapter
import herdr_calls
import herdr_identity
import herdr_write
from herdr_replacement_process import (
    ObservedProcess,
    ProcessIds,
    ProcessReader,
    proc_process,
    proc_process_ids,
)

_FOREGROUND_UNREADABLE = "Herdr foreground process is unavailable"
_SHELL_UNREADABLE = "Herdr retained shell has no stable kernel identity"
_GROUP_UNREADABLE = "Herdr foreground group or retained shell is not fully observable"

__all__: list[str] = [
    "GroupTerminator",
    "ObservedProcess",
    "ProcessIds",
    "ProcessReader",
    "ReplacementController",
    "ReplacementOutcome",
    "ReplacementSnapshot",
    "ReplacementWriter",
    "proc_process",
    "proc_process_ids",
    "terminate_process_group",
]


@dataclass(frozen=True, kw_only=True)
class ReplacementSnapshot:
    """The retained shell and every observed member of its foreground group."""

    shell: ObservedProcess
    foreground_group: int
    processes: tuple[ObservedProcess, ...]


@dataclass(frozen=True, kw_only=True)
class ReplacementOutcome:
    """A native mutation result, retaining write uncertainty when one exists."""

    ok: bool
    error: str
    effect_unknown: bool = False


class GroupTerminator(Protocol):
    def __call__(self, *, process_group: int) -> None: ...


class ReplacementWriter(Protocol):
    def launch(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        cwd: str,
        command: str,
        env: Mapping[str, str | None],
    ) -> herdr_write.WriteOutcome: ...


def terminate_process_group(*, process_group: int) -> None:
    """Send the replacement's sole termination signal."""
    os.killpg(process_group, signal.SIGTERM)


@dataclass(frozen=True, kw_only=True)
class ReplacementController:
    """Bind native effects to one exact Herdr server generation and pane."""

    observer: herdr_adapter.ForegroundObserver
    writer: ReplacementWriter
    process_of: ProcessReader = proc_process
    process_ids: ProcessIds = proc_process_ids
    terminate_group: GroupTerminator = terminate_process_group
    login_shells: frozenset[str] = field(default_factory=_herdr_shell_identity.system_login_shells)

    @staticmethod
    def _foreground(
        *,
        observer: herdr_adapter.ForegroundObserver,
        target: herdr_identity.HerdrPaneTarget,
    ) -> herdr_calls.ForegroundProcess:
        reading = observer.foreground(target=target)
        if not reading.ok or reading.process is None:
            raise OSError(reading.error or _FOREGROUND_UNREADABLE)
        return reading.process

    def snapshot(self, *, target: herdr_identity.HerdrPaneTarget) -> ReplacementSnapshot:
        """Read the exact pane plus stable kernel identities for its foreground group."""
        foreground = self._foreground(observer=self.observer, target=target)
        shell = self.process_of(pid=foreground.shell_pid)
        if shell is None:
            raise OSError(_SHELL_UNREADABLE)
        processes = tuple(
            process
            for pid in self.process_ids()
            if (process := self.process_of(pid=pid)) is not None
            and (process.process_group == foreground.process_group_id or process.pid == shell.pid)
        )
        leader = next(
            (process for process in processes if process.pid == foreground.process_group_id),
            None,
        )
        shell_supported = str(Path(shell.executable).resolve()) in self.login_shells
        if (
            leader is None
            or not any(process.pid == shell.pid for process in processes)
            or not shell_supported
            or shell.process_group != shell.pid
            or leader.session_id != shell.session_id
        ):
            raise OSError(_GROUP_UNREADABLE)
        return ReplacementSnapshot(
            shell=shell,
            foreground_group=foreground.process_group_id,
            processes=tuple(sorted(processes, key=lambda process: process.pid)),
        )

    def terminate(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        process_group: int,
        expected: ReplacementSnapshot | None,
    ) -> ReplacementOutcome:
        """Reverify the acting connection and send at most one signal to its child group."""
        try:
            foreground = self._foreground(observer=self.observer, target=target)
            shell = self.process_of(pid=foreground.shell_pid)
            leader = self.process_of(pid=process_group)
            expected_group = (
                ()
                if expected is None
                else tuple(
                    process
                    for process in expected.processes
                    if process.process_group == process_group
                )
            )
            group_unchanged = all(
                self.process_of(pid=process.pid) == process for process in expected_group
            )
            safe = (
                expected is not None
                and foreground.process_group_id == process_group
                and process_group not in {foreground.shell_pid, target.server_pid}
                and shell is not None
                and shell == expected.shell
                and leader is not None
                and leader.process_group == process_group
                and leader.session_id == shell.session_id
                and bool(expected_group)
                and group_unchanged
            )
            if not safe:
                return ReplacementOutcome(
                    ok=False,
                    error="Herdr foreground ownership changed before termination",
                )
            self.terminate_group(process_group=process_group)
        except OSError as exc:
            return ReplacementOutcome(ok=False, error=str(exc))
        return ReplacementOutcome(ok=True, error="")

    def launch(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        cwd: str,
        command: str,
        env: Mapping[str, str | None],
    ) -> ReplacementOutcome:
        """Submit one exact launch request; ambiguity is returned, never replayed here."""
        outcome = self.writer.launch(target=target, cwd=cwd, command=command, env=env)
        return ReplacementOutcome(
            ok=outcome.ok,
            error=outcome.error,
            effect_unknown=outcome.effect_unknown,
        )
