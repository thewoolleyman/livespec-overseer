"""Process proof for a Codex successor that still exposes a rollout."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _herdr_replacement_process
import _supervisor_launch
import registry
import signals

if TYPE_CHECKING:
    from _codex_session_models import CodexSession
    from _supervisor_core import Supervisor

__all__: list[str] = ["carrier_from_live_rollout"]


def carrier_from_live_rollout(
    *,
    sup: Supervisor,
    track: registry.Track,
    snapshot: _herdr_replacement_process.ReplacementSnapshot,
    live: CodexSession,
    predecessor: object,
) -> tuple[_herdr_replacement_process.ProcessObservation | None, str | None]:
    """Require the observed rollout to belong to the fresh retained-shell carrier."""
    if (
        live.session_id == predecessor
        or _supervisor_launch.canonical_codex_session_id(value=live.session_id) is None
        or not signals.path_in_repo(pane_current_path=live.cwd, repo=track.repo)
    ):
        return None, "fresh Codex rollout is not yet observable in the original pane"
    starttime = sup.starttime_of(pid=live.pid)
    if starttime is None:
        return None, "fresh Codex process generation is not readable"
    carrier = next((process for process in snapshot.processes if process.pid == live.pid), None)
    if carrier is None:
        return None, "Codex successor is not a fresh process in the retained shell"
    return carrier, None
