"""Render a verified terminal ownership claim as its durable coordinate."""

from __future__ import annotations

import herdr_identity
import terminal_ownership
import terminal_probes

__all__: list[str] = ["qualified_coordinate"]


def qualified_coordinate(*, claim: terminal_ownership.OwnershipClaim) -> str | None:
    """Qualify named instances while retaining default-tmux legacy declaration."""
    coordinates = {
        herdr_identity.HERDR_BACKEND: herdr_identity.encode_herdr_target(
            target=herdr_identity.HerdrPaneTarget(
                socket_path=claim.socket_path,
                server_pid=claim.server_pid,
                server_starttime=claim.server_starttime,
                pane_id=claim.pane_id,
            )
        ),
        herdr_identity.TMUX_BACKEND: herdr_identity.encode_tmux_target(
            target=herdr_identity.TmuxPaneTarget(
                socket_path=claim.socket_path,
                server_pid=claim.server_pid,
                server_starttime=claim.server_starttime,
                pane_id=claim.pane_id,
            )
        ),
    }
    return (
        None
        if claim.backend == herdr_identity.TMUX_BACKEND
        and claim.socket_path == terminal_probes.DEFAULT_TMUX_ENDPOINT
        else coordinates.get(claim.backend)
    )
