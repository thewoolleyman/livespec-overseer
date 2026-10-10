"""Route durable pane coordinates to their recorded terminal instance."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import partial
from typing import Protocol, cast

import claude_sessions
import herdr_adapter
import herdr_identity
import herdr_write
import pane_discovery
import terminal_ownership
import terminal_probes
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


class HerdrObserver(Protocol):
    def identify(self, *, socket_path: str) -> herdr_adapter.InstanceIdentification: ...

    def list_panes(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.PaneListing: ...

    def capture_pane(
        self, *, target: herdr_identity.HerdrPaneTarget, retain_ansi: bool = True
    ) -> herdr_adapter.PaneCapture: ...

    def foreground(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.ForegroundReading: ...


class HerdrInput(Protocol):
    def bracketed_paste(
        self, *, target: herdr_identity.HerdrPaneTarget, text: str
    ) -> herdr_write.WriteOutcome: ...

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_write.WriteOutcome: ...


@dataclass(kw_only=True)
class MixedPaneDriver:
    """A pane driver that resolves each qualified Herdr coordinate independently."""

    tmux: PaneDriver = field(default_factory=tmuxio.TmuxIO)
    herdr: HerdrObserver = field(default_factory=herdr_adapter.HerdrAdapter)
    herdr_writer: HerdrInput = field(default_factory=herdr_write.HerdrWriter)
    herdr_endpoints: Callable[[], Iterable[str]] = field(
        default_factory=lambda: partial(tuple, _DEFAULT_HERDR_ENDPOINTS)
    )
    coordinates: set[str] = field(default_factory=set)

    def register_coordinates(self, *, coordinates: Iterable[str]) -> None:
        self.coordinates.update(coordinates)

    def _herdr_target(self, *, value: str) -> herdr_identity.HerdrPaneTarget | None:
        target = herdr_identity.decode_target(value=value).herdr
        if target is not None:
            self.coordinates.add(value)
        return target

    def capture_pane(self, *, session: str) -> str:
        target = self._herdr_target(value=session)
        if target is None:
            return self.tmux.capture_pane(session=session)
        return self.herdr.capture_pane(target=target, retain_ansi=True).text

    def pane_id(self, *, session: str) -> str | None:
        target = self._herdr_target(value=session)
        if target is None:
            return self.tmux.pane_id(session=session)
        return session

    def _foreground(self, *, session: str) -> herdr_adapter.ForegroundReading | None:
        target = self._herdr_target(value=session)
        return None if target is None else self.herdr.foreground(target=target)

    def pane_pid(self, *, session: str) -> int | None:
        reading = self._foreground(session=session)
        if reading is None:
            return self.tmux.pane_pid(session=session)
        return cast(int | None, getattr(reading.process, "shell_pid", None))

    def pane_current_command(self, *, session: str) -> str | None:
        reading = self._foreground(session=session)
        if reading is None:
            return self.tmux.pane_current_command(session=session)
        return cast(str | None, getattr(reading.process, "name", None))

    def pane_current_path(self, *, session: str) -> str | None:
        reading = self._foreground(session=session)
        if reading is None:
            return self.tmux.pane_current_path(session=session)
        return cast(str | None, getattr(reading.process, "cwd", None))

    def session_exists(self, *, session: str) -> bool:
        target = self._herdr_target(value=session)
        if target is None:
            return self.tmux.session_exists(session=session)
        listing = self.herdr.list_panes(target=target)
        return listing.ok and any(pane.pane_id == target.pane_id for pane in listing.panes)

    def pane_pid_sessions(self) -> dict[int, str]:
        out = self.tmux.pane_pid_sessions()
        recorded = (
            herdr_identity.decode_target(value=coordinate).herdr for coordinate in self.coordinates
        )
        targets = set(filter(None, recorded))
        observer = cast(pane_discovery.DiscoveryObserver, self.herdr)
        endpoints = (
            self.herdr_endpoints() if callable(getattr(self.herdr, "identify", None)) else ()
        )
        targets.update(pane_discovery.discovered_targets(observer=observer, endpoints=endpoints))
        out.update(pane_discovery.pid_coordinates(observer=observer, targets=targets))
        return out

    def submit_prompt_once(self, *, session: str, text: str) -> tuple[bool, bool]:
        """Use Herdr's retained-shell-checked writes once, without uncertain replay."""
        target = cast(herdr_identity.HerdrPaneTarget, self._herdr_target(value=session))
        pasted = self.herdr_writer.bracketed_paste(target=target, text=text)
        submitted = self.herdr_writer.send_enter(target=target)
        return all((pasted.ok, submitted.ok)), not pasted.ok


def default_pane_driver() -> PaneDriver:
    return cast(PaneDriver, MixedPaneDriver())


def register_coordinates(*, driver: PaneDriver, coordinates: Iterable[str]) -> None:
    if isinstance(driver, MixedPaneDriver):
        driver.register_coordinates(coordinates=coordinates)


def _herdr_coordinate(*, claim: terminal_ownership.OwnershipClaim) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=claim.socket_path,
            server_pid=claim.server_pid,
            server_starttime=claim.server_starttime,
            pane_id=claim.pane_id,
        )
    )


def current_process_coordinate() -> str | None:
    """Exact qualified Herdr owner of this process, proven by live ancestry."""
    selected = terminal_ownership.select_owner(
        pid=PROCESS_PID(),
        environ=dict(os.environ),
        probes=OWNERSHIP_PROBES(),
        ppid_of=PROCESS_PPID,
    )
    claim = selected.claim
    renderers: dict[str, Callable[[], str | None]] = {
        herdr_identity.HERDR_BACKEND: lambda: _herdr_coordinate(
            claim=cast(terminal_ownership.OwnershipClaim, claim)
        )
    }
    return renderers.get(getattr(claim, "backend", ""), lambda: None)()
