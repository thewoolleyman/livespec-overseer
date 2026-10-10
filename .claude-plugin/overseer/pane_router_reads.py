"""Observation routing for legacy and instance-qualified terminal panes."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol, cast

import herdr_adapter
import herdr_identity
import pane_discovery
import tmux_bootstrap_driver
import tmux_process
import tmuxio
from tmuxio_protocols import PaneDriver

__all__: list[str] = ["HerdrObserver", "PaneRoutingReads"]


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


@dataclass(kw_only=True)
class PaneRoutingReads:
    """Read panes without losing a qualified target's recorded instance."""

    tmux: PaneDriver
    herdr: HerdrObserver
    herdr_endpoints: Callable[[], Iterable[str]]
    tmux_run: tmux_process.TextProcessRun
    coordinates: set[str]

    def decode(self, *, value: str) -> herdr_identity.TargetDecoding:
        decoded = herdr_identity.decode_target(value=value)
        if decoded.herdr is not None or decoded.tmux is not None:
            self.coordinates.add(value)
        return decoded

    def tmux_driver(self, *, target: herdr_identity.TmuxPaneTarget) -> tmuxio.TmuxIO:
        socket_driver = tmux_bootstrap_driver.socket_scoped_driver(
            socket_path=target.socket_path,
            run=self.tmux_run,
        )
        return cast(
            tmuxio.TmuxIO,
            tmux_bootstrap_driver.bind_server_generation(
                driver=socket_driver,
                server_pid=target.server_pid,
                server_starttime=target.server_starttime,
                split_height_percent=50,
            ),
        )

    def capture_pane(self, *, session: str) -> str:
        decoded = self.decode(value=session)
        if decoded.herdr is not None:
            return self.herdr.capture_pane(target=decoded.herdr, retain_ansi=True).text
        if decoded.tmux is not None:
            return self.tmux_driver(target=decoded.tmux).capture_pane(session=decoded.tmux.pane_id)
        return "" if decoded.error else self.tmux.capture_pane(session=session)

    def pane_id(self, *, session: str) -> str | None:
        decoded = self.decode(value=session)
        if decoded.herdr is not None:
            return session
        if decoded.tmux is not None:
            pane = self.tmux_driver(target=decoded.tmux).pane_id(session=decoded.tmux.pane_id)
            return session if pane == decoded.tmux.pane_id else None
        return None if decoded.error else self.tmux.pane_id(session=session)

    def pane_pid(self, *, session: str) -> int | None:
        decoded = self.decode(value=session)
        if decoded.herdr is not None:
            reading = self.herdr.foreground(target=decoded.herdr)
            return cast(int | None, getattr(reading.process, "shell_pid", None))
        if decoded.tmux is not None:
            return self.tmux_driver(target=decoded.tmux).pane_pid(session=decoded.tmux.pane_id)
        return None if decoded.error else self.tmux.pane_pid(session=session)

    def pane_current_command(self, *, session: str) -> str | None:
        decoded = self.decode(value=session)
        if decoded.herdr is not None:
            reading = self.herdr.foreground(target=decoded.herdr)
            return cast(str | None, getattr(reading.process, "name", None))
        if decoded.tmux is not None:
            return self.tmux_driver(target=decoded.tmux).pane_current_command(
                session=decoded.tmux.pane_id
            )
        return None if decoded.error else self.tmux.pane_current_command(session=session)

    def pane_current_path(self, *, session: str) -> str | None:
        decoded = self.decode(value=session)
        if decoded.herdr is not None:
            reading = self.herdr.foreground(target=decoded.herdr)
            return cast(str | None, getattr(reading.process, "cwd", None))
        if decoded.tmux is not None:
            return self.tmux_driver(target=decoded.tmux).pane_current_path(
                session=decoded.tmux.pane_id
            )
        return None if decoded.error else self.tmux.pane_current_path(session=session)

    def session_exists(self, *, session: str) -> bool:
        decoded = self.decode(value=session)
        if decoded.herdr is not None:
            listing = self.herdr.list_panes(target=decoded.herdr)
            return listing.ok and any(
                pane.pane_id == decoded.herdr.pane_id for pane in listing.panes
            )
        if decoded.tmux is not None:
            return (
                self.tmux_driver(target=decoded.tmux).pane_id(session=decoded.tmux.pane_id)
                == decoded.tmux.pane_id
            )
        return False if decoded.error else self.tmux.session_exists(session=session)

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
        for coordinate in self.coordinates:
            target = herdr_identity.decode_target(value=coordinate).tmux
            if target is None:
                continue
            pid = self.tmux_driver(target=target).pane_pid(session=target.pane_id)
            pid_mapping = {pid: coordinate}
            _ = pid_mapping.pop(None, None)
            out.update(cast(dict[int, str], pid_mapping))
        return out
