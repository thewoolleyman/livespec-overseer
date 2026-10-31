"""One tick's shared, read-only Herdr observations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Protocol

import herdr_adapter
import herdr_identity

__all__: list[str] = ["HerdrCycleCache"]

_CLAUDE_IDENTITY_PARTS = 4


class HerdrObserver(Protocol):
    """The observation calls whose results are stable within one tick."""

    def identify(self, *, socket_path: str) -> herdr_adapter.InstanceIdentification: ...

    def list_panes(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.PaneListing: ...

    def foreground(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.ForegroundReading: ...


@dataclass(kw_only=True)
class HerdrCycleCache:
    """Memoize exact Herdr reads only for the daemon's current tick."""

    listings: dict[str, herdr_adapter.PaneListing] = field(default_factory=dict)
    identities: dict[str, herdr_adapter.InstanceIdentification] = field(default_factory=dict)
    foregrounds: dict[str, herdr_adapter.ForegroundReading] = field(default_factory=dict)
    relocations: dict[tuple[str, str | None], str | None] = field(default_factory=dict)

    def clear(self) -> None:
        """Forget all observations before the next live supervision cycle."""
        self.listings.clear()
        self.identities.clear()
        self.foregrounds.clear()
        self.relocations.clear()

    def identify(
        self, *, observer: HerdrObserver, socket_path: str
    ) -> herdr_adapter.InstanceIdentification:
        cached = self.identities.get(socket_path)
        if cached is None:
            cached = observer.identify(socket_path=socket_path)
            self.identities[socket_path] = cached
        return cached

    def listing(
        self, *, observer: HerdrObserver, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.PaneListing:
        key = herdr_identity.herdr_instance_key(target=target)
        cached = self.listings.get(key)
        if cached is None:
            cached = observer.list_panes(target=target)
            self.listings[key] = cached
        return cached

    def foreground(
        self, *, observer: HerdrObserver, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.ForegroundReading:
        key = herdr_identity.encode_herdr_target(target=target)
        cached = self.foregrounds.get(key)
        if cached is None:
            cached = observer.foreground(target=target)
            self.foregrounds[key] = cached
        return cached

    def relocated_coordinate(
        self,
        *,
        observer: HerdrObserver,
        target: herdr_identity.HerdrPaneTarget,
        session: str,
        observed_session_identity: str | None,
        starttime_of: Callable[..., str | None],
    ) -> str | None:
        key = (session, observed_session_identity)
        if key in self.relocations:
            return self.relocations[key]
        peer = self.identify(observer=observer, socket_path=target.socket_path).peer
        generation = getattr(peer, "pid", None), getattr(peer, "starttime", None)
        if generation != (target.server_pid, target.server_starttime):
            self.relocations[key] = None
            return None
        parts = (observed_session_identity or "").split(":", 3)
        if len(parts) != _CLAUDE_IDENTITY_PARTS or parts[0] != "claude":
            self.relocations[key] = None
            return None
        try:
            recorded_identity = int(parts[1]), parts[2]
        except ValueError:
            self.relocations[key] = None
            return None
        matches: list[herdr_identity.HerdrPaneTarget] = []
        for pane in self.listing(observer=observer, target=target).panes:
            candidate = replace(target, pane_id=pane.pane_id)
            process = self.foreground(observer=observer, target=candidate).process
            if (
                process is not None
                and (
                    process.process_group_id,
                    starttime_of(pid=process.process_group_id),
                )
                == recorded_identity
            ):
                matches.append(candidate)
        result = (
            None if len(matches) != 1 else herdr_identity.encode_herdr_target(target=matches[0])
        )
        self.relocations[key] = result
        return result
