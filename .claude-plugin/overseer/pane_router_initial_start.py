"""Initial-agent lifecycle entry points for the mixed pane facade."""

from __future__ import annotations

from typing import Protocol

import herdr_initial_start

__all__: list[str] = [
    "InitialRouteHost",
    "create_initial_pane",
    "created_initial_pane_persisted",
    "finish_initial_agent",
    "launch_initial_agent",
    "pending_initial_start",
    "preserve_initial_pane",
]


class InitialRouteHost(Protocol):
    initial_start: herdr_initial_start.HerdrInitialStart


def pending_initial_start(self: InitialRouteHost, *, repo: str, topic: str, session: str) -> str:
    return self.initial_start.pending_initial_start(repo=repo, topic=topic, session=session)


def create_initial_pane(self: InitialRouteHost, *, source: str, name: str, cwd: str) -> object:
    return self.initial_start.create_initial_pane(source=source, name=name, cwd=cwd)


def created_initial_pane_persisted(
    self: InitialRouteHost, *, repo: str, topic: str, session: str
) -> None:
    self.initial_start.created_initial_pane_persisted(repo=repo, topic=topic, session=session)


def launch_initial_agent(
    self: InitialRouteHost,
    *,
    session: str,
    cwd: str,
    command: str,
    env: object,
    expected_process: str,
) -> object:
    return self.initial_start.launch_initial_agent(
        session=session,
        cwd=cwd,
        command=command,
        env=env,
        expected_process=expected_process,
    )


def finish_initial_agent(
    self: InitialRouteHost, *, repo: str, session: str, unresolved: bool
) -> None:
    self.initial_start.finish_initial_agent(repo=repo, session=session, unresolved=unresolved)


def preserve_initial_pane(self: InitialRouteHost, *, session: str) -> bool:
    return self.initial_start.preserve_initial_pane(session=session)
