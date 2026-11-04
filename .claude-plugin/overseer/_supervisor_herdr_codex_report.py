"""Backend agent-session reporting after Codex successor proof."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import _herdr_replacement_store
import _supervisor_launch
import herdr_write
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["report_successor_thread"]


class AgentSessionReporter(Protocol):
    def __call__(
        self, *, session: str, source: str, agent_session_id: str
    ) -> herdr_write.WriteOutcome: ...


def report_successor_thread(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    current: dict[str, object],
    record_path: Path,
) -> None:
    """Report the confirmed thread without letting a backend rejection void proof."""
    thread = current.get("successor_thread")
    reporter = cast(AgentSessionReporter | None, getattr(sup.tmux, "report_agent_session", None))
    if (
        current.get("backend_report") is not None
        or not isinstance(thread, str)
        or not callable(reporter)
    ):
        return
    outcome = reporter(session=target, source="overseerd", agent_session_id=thread)
    current["backend_report"] = {"thread": thread, "accepted": outcome.ok}
    _herdr_replacement_store.durable_write(path=record_path, value=current)
    if not outcome.ok:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message=f"Herdr rejected fresh Codex agent-session report: {outcome.error}",
            condition="herdr-agent-session-report-rejected",
        )
