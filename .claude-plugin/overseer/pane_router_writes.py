"""Mutation routing for legacy and instance-qualified terminal panes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial

import herdr_identity
import pane_router_reads
import pane_router_submit
import pane_router_submit_signals

__all__: list[str] = ["HerdrInput", "PaneRoutingWrites"]

HerdrInput = pane_router_submit_signals.HerdrInput


@dataclass(kw_only=True)
class PaneRoutingWrites:
    """Mutate only the backend instance named by the durable coordinate."""

    reads: pane_router_reads.PaneRoutingReads
    herdr_writer: HerdrInput
    prompt_states: dict[str, pane_router_submit_signals.PromptState]

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

    def submit_prompt_once(
        self,
        *,
        session: str,
        text: str,
        expect_codex: bool,
        sleep: Callable[[float], None],
    ) -> tuple[bool, bool]:
        """Observe Herdr paste and submit effects without replaying uncertainty."""
        return pane_router_submit.PromptSubmitter(
            reads=self.reads,
            writer=self.herdr_writer,
            states=self.prompt_states,
        ).submit_prompt_once(
            session=session,
            text=text,
            expect_codex=expect_codex,
            sleep=sleep,
        )
