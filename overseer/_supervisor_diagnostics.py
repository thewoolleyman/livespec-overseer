"""_supervisor_diagnostics — daemon event-history and operator alert lines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
import streams
from _supervisor_config import iso_now, track_key

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["AlertRequest", "alert", "log", "log_claude_build", "surface"]


@dataclass(frozen=True, kw_only=True)
class AlertRequest:
    sup: Supervisor
    repo: str
    topic: str
    session: str | None
    pane: str | None
    message: str
    condition: str


def log(*, message: str) -> None:
    streams.write_stderr(text=f"{iso_now()} overseer: {message}\n")


def log_claude_build(*, sup: Supervisor, phase: str) -> None:
    version = sup.claude_version_of() or "unavailable"
    log(message=f"claude build at {phase}: {version}")


def surface(*, message: str) -> None:
    """Surface a DAEMON-level alert to the operator."""
    streams.write_stderr(text=f"{iso_now()} overseer[SURFACE]: {message}\n")


def alert(*, request: AlertRequest) -> None:
    """Surface a TRACK-scoped alert that always names WHERE to act.

    Every track alert carries the plan topic, its repo, the tmux SESSION and PANE
    holding it, and a copy-pasteable jump command. ``repo::topic`` alone tells the
    operator WHAT is stuck but never WHERE to go.

    EDGE-TRIGGERED: emitted when a track ENTERS a condition, or the condition's text
    changes, instead of once per tick.
    """
    where = (
        f"tmux session '{request.session}' pane {request.pane}"
        if request.session
        else "no live tmux session"
    )
    jump = f" — jump: tmux switch-client -t {request.session}" if request.session else ""
    line = (
        f"{request.topic} ({registry.repo_slug(repo=request.repo)}) — "
        f"{request.message} [{where}]{jump}"
    )
    key = (*track_key(repo=request.repo, topic=request.topic), request.condition)
    if request.sup.alerted.get(key) == line:
        return
    request.sup.alerted[key] = line
    surface(message=line)
