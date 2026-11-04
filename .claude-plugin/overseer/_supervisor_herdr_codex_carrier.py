"""Carrier proof for a fresh Herdr Codex successor, with or without a rollout fd."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import _herdr_replacement_process
import _supervisor_launch
import signals
from _codex_session_models import CodexSession

if TYPE_CHECKING:
    import registry
    from _supervisor_core import Supervisor

__all__: list[str] = ["carrier_from_live_rollout", "carrier_without_rollout"]


def carrier_from_live_rollout(
    *,
    sup: Supervisor,
    track: registry.Track,
    snapshot: _herdr_replacement_process.ReplacementSnapshot,
    live: CodexSession,
    predecessor: object,
) -> tuple[_herdr_replacement_process.ProcessObservation | None, str | None]:
    """Prove the live-rollout carrier is still the fresh retained-shell process."""
    if (
        live.session_id == predecessor
        or _supervisor_launch.canonical_codex_session_id(value=live.session_id) is None
        or not signals.path_in_repo(pane_current_path=live.cwd, repo=track.repo)
    ):
        return None, "fresh Codex rollout is not yet observable in the original pane"
    starttime = sup.starttime_of(pid=live.pid)
    carrier = next((process for process in snapshot.processes if process.pid == live.pid), None)
    if starttime is None:
        return None, "fresh Codex process generation is not readable"
    if carrier is None or carrier.starttime != starttime:
        return None, "Codex successor is not a fresh process in the retained shell"
    return carrier, None


def carrier_without_rollout(
    *, sup: Supervisor, snapshot: _herdr_replacement_process.ReplacementSnapshot
) -> tuple[_herdr_replacement_process.ProcessObservation | None, str | None]:
    """Prove the one fresh Codex carrier when its shared server owns no rollout fd."""
    if not callable(getattr(sup.tmux, "report_agent_session", None)):
        return None, "fresh Codex rollout is not yet observable in the original pane"
    carriers = [
        process
        for process in snapshot.processes
        if Path(process.executable).name == "codex" and process.pid != snapshot.foreground_group
    ]
    if len(carriers) != 1:
        return None, "fresh Codex successor is not uniquely observable in the retained shell"
    return carriers[0], None
