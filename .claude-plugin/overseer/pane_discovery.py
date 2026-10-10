"""Discover exact Herdr pane coordinates and join their live process roots."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Protocol

import herdr_adapter
import herdr_identity

__all__: list[str] = ["DiscoveryObserver", "discovered_targets", "pid_coordinates"]


class DiscoveryObserver(Protocol):
    def identify(self, *, socket_path: str) -> herdr_adapter.InstanceIdentification: ...

    def list_panes(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.PaneListing: ...

    def foreground(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.ForegroundReading: ...


def discovered_targets(
    *, observer: DiscoveryObserver, endpoints: Iterable[str]
) -> set[herdr_identity.HerdrPaneTarget]:
    """Every readable pane, qualified by the peer generation that answered."""
    targets: set[herdr_identity.HerdrPaneTarget] = set()
    for endpoint in endpoints:
        identified = observer.identify(socket_path=endpoint)
        peers = () if identified.peer is None else (identified.peer,)
        for peer in peers:
            probe = herdr_identity.HerdrPaneTarget(
                socket_path=endpoint,
                server_pid=peer.pid,
                server_starttime=peer.starttime,
                pane_id="",
            )
            listing = observer.list_panes(target=probe)
            targets.update(replace(probe, pane_id=row.pane_id) for row in listing.panes)
    return targets


def pid_coordinates(
    *,
    observer: DiscoveryObserver,
    targets: Iterable[herdr_identity.HerdrPaneTarget],
) -> dict[int, str]:
    """Pane shell/group-leader PID to its exact durable coordinate."""
    out: dict[int, str] = {}
    for target in targets:
        reading = observer.foreground(target=target)
        for process in filter(None, (reading.process,)):
            coordinate = herdr_identity.encode_herdr_target(target=target)
            out[process.shell_pid] = coordinate
            out[process.process_group_id] = coordinate
    return out
