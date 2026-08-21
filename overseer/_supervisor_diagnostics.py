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
    operator WHAT is stuck but never WHERE to go — they were left to hunt for the
    session by hand (maintainer 2026-07-14).

    This is load-bearing for the notify-never-block contract (invariant 8): because
    the overseer NEVER prompts on a track's behalf, this line is the operator's ONLY
    handover, so it MUST be self-sufficient. Every new track-scoped alert goes
    through here — never a bare ``surface`` with an f-string of ``repo::topic``.

    EDGE-TRIGGERED: emitted when a track ENTERS a condition (or the condition's text
    changes), NOT once per tick. The log is the daemon's EVENT HISTORY — the surface
    the bottom pane reads to answer "what happened, and when?" — while CURRENT state
    is owned by the re-rendered table + its ``NEEDS YOU`` block. Re-emitting an
    unchanged alert every tick buried that history in thousands of identical lines (a
    track blocked overnight logged ~3,000 of them) and answered a question the table
    already answers better. The re-arm is in :meth:`evaluate`: when a track returns to
    a healthy status its entry is dropped, so the NEXT time it goes bad it reports
    again.
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
