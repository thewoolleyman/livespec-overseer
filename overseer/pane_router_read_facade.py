"""Read-only public entry points for the mixed pane facade."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

import pane_router_reads
import tmux_process
from tmuxio_protocols import PaneDriver

__all__: list[str] = [
    "ReadRouteHost",
    "capture_pane",
    "pane_by_title",
    "pane_current_command",
    "pane_current_path",
    "pane_id",
    "pane_pid",
    "pane_pid_sessions",
    "reads",
    "register_coordinates",
    "session_exists",
]


class ReadRouteHost(Protocol):
    tmux: PaneDriver
    herdr: pane_router_reads.HerdrObserver
    herdr_endpoints: Callable[[], Iterable[str]]
    tmux_run: tmux_process.TextProcessRun
    coordinates: set[str]


def reads(*, driver: ReadRouteHost) -> pane_router_reads.PaneRoutingReads:
    return pane_router_reads.PaneRoutingReads(
        tmux=driver.tmux,
        herdr=driver.herdr,
        herdr_endpoints=driver.herdr_endpoints,
        tmux_run=driver.tmux_run,
        coordinates=driver.coordinates,
    )


def register_coordinates(self: ReadRouteHost, *, coordinates: Iterable[str]) -> None:
    self.coordinates.update(coordinates)


def capture_pane(self: ReadRouteHost, *, session: str) -> str:
    return reads(driver=self).capture_pane(session=session)


def pane_id(self: ReadRouteHost, *, session: str) -> str | None:
    return reads(driver=self).pane_id(session=session)


def pane_pid(self: ReadRouteHost, *, session: str) -> int | None:
    return reads(driver=self).pane_pid(session=session)


def pane_current_command(self: ReadRouteHost, *, session: str) -> str | None:
    return reads(driver=self).pane_current_command(session=session)


def pane_current_path(self: ReadRouteHost, *, session: str) -> str | None:
    return reads(driver=self).pane_current_path(session=session)


def session_exists(self: ReadRouteHost, *, session: str) -> bool:
    return reads(driver=self).session_exists(session=session)


def pane_pid_sessions(self: ReadRouteHost) -> dict[int, str]:
    return reads(driver=self).pane_pid_sessions()


def pane_by_title(self: ReadRouteHost, *, pane: str, title: str) -> str | None:
    decoded = reads(driver=self).decode(value=pane)
    if decoded.herdr is not None or decoded.tmux is not None or decoded.error:
        return None
    return self.tmux.pane_by_title(pane=pane, title=title)
