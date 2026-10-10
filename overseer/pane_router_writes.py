"""Mutation routing for legacy and instance-qualified terminal panes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Protocol, cast

import herdr_identity
import herdr_write
import pane_router_reads

__all__: list[str] = ["HerdrInput", "PaneRoutingWrites"]


class HerdrInput(Protocol):
    def bracketed_paste(
        self, *, target: herdr_identity.HerdrPaneTarget, text: str
    ) -> herdr_write.WriteOutcome: ...

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_write.WriteOutcome: ...


@dataclass(kw_only=True)
class PaneRoutingWrites:
    """Mutate only the backend instance named by the durable coordinate."""

    reads: pane_router_reads.PaneRoutingReads
    herdr_writer: HerdrInput

    def send_keys(self, *, session: str, keys: str) -> bool:
        decoded = self.reads.decode(value=session)
        if decoded.tmux is not None:
            return self.reads.tmux_driver(target=decoded.tmux).send_keys(
                session=decoded.tmux.pane_id,
                keys=keys,
            )
        routes: dict[str, Callable[[], bool]] = {
            herdr_identity.HERDR_BACKEND: partial(bool),
            "": partial(bool),
            herdr_identity.TMUX_BACKEND: partial(
                self.reads.tmux.send_keys,
                session=session,
                keys=keys,
            ),
        }
        return routes[decoded.backend]()

    def bracketed_paste(self, *, session: str, text: str) -> bool:
        decoded = self.reads.decode(value=session)
        if decoded.tmux is not None:
            return self.reads.tmux_driver(target=decoded.tmux).bracketed_paste(
                session=decoded.tmux.pane_id,
                text=text,
            )
        routes: dict[str, Callable[[], bool]] = {
            herdr_identity.HERDR_BACKEND: partial(bool),
            "": partial(bool),
            herdr_identity.TMUX_BACKEND: partial(
                self.reads.tmux.bracketed_paste,
                session=session,
                text=text,
            ),
        }
        return routes[decoded.backend]()

    def respawn_pane(
        self,
        *,
        session: str,
        cwd: str,
        command: str,
        env: Mapping[str, str | None] | None = None,
    ) -> bool:
        decoded = self.reads.decode(value=session)
        if decoded.herdr is not None or decoded.error:
            return False
        if decoded.tmux is not None:
            return self.reads.tmux_driver(target=decoded.tmux).respawn_pane(
                session=decoded.tmux.pane_id,
                cwd=cwd,
                command=command,
                env=env,
            )
        return self.reads.tmux.respawn_pane(
            session=session,
            cwd=cwd,
            command=command,
            env=env,
        )

    def new_session(self, *, name: str, cwd: str) -> bool:
        decoded = self.reads.decode(value=name)
        if decoded.herdr is not None or decoded.tmux is not None or decoded.error:
            return False
        return self.reads.tmux.new_session(name=name, cwd=cwd)

    def kill_session(self, *, session: str) -> bool:
        decoded = self.reads.decode(value=session)
        if decoded.herdr is not None or decoded.tmux is not None or decoded.error:
            return False
        return self.reads.tmux.kill_session(session=session)

    def rename_window(self, *, pane: str, name: str) -> bool:
        decoded = self.reads.decode(value=pane)
        if decoded.tmux is not None:
            return self.reads.tmux_driver(target=decoded.tmux).rename_window(
                pane=decoded.tmux.pane_id,
                name=name,
            )
        routes: dict[str, Callable[[], bool]] = {
            herdr_identity.HERDR_BACKEND: partial(bool),
            "": partial(bool),
            herdr_identity.TMUX_BACKEND: partial(
                self.reads.tmux.rename_window,
                pane=pane,
                name=name,
            ),
        }
        return routes[decoded.backend]()

    def submit_prompt_once(self, *, session: str, text: str) -> tuple[bool, bool]:
        """Use Herdr's retained-shell-checked writes once, without uncertain replay."""
        target = cast(
            herdr_identity.HerdrPaneTarget,
            self.reads.decode(value=session).herdr,
        )
        pasted = self.herdr_writer.bracketed_paste(target=target, text=text)
        submissions: dict[bool, Callable[[], herdr_write.WriteOutcome]] = {
            False: partial(
                herdr_write.WriteOutcome,
                ok=False,
                error=pasted.error,
                effect_unknown=pasted.effect_unknown,
            ),
            True: partial(self.herdr_writer.send_enter, target=target),
        }
        submitted = submissions[pasted.ok]()
        return submitted.ok, submitted.effect_unknown
