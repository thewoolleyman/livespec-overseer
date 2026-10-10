"""Render a verified terminal ownership claim as its durable coordinate."""

from __future__ import annotations

import shlex
from dataclasses import dataclass

import herdr_identity
import terminal_ownership
import terminal_probes

__all__: list[str] = [
    "HerdrAttention",
    "alert_attention",
    "herdr_attention",
    "qualified_coordinate",
]


@dataclass(frozen=True, kw_only=True)
class HerdrAttention:
    """Operator-facing identity and native jump for one qualified Herdr pane."""

    display: str
    where: str
    jump: str


def herdr_attention(*, coordinate: str) -> HerdrAttention | None:
    """Render a qualified Herdr coordinate without treating it as tmux."""
    target = herdr_identity.decode_target(value=coordinate).herdr
    if target is None:
        return None
    return HerdrAttention(
        display=(
            f"{target.socket_path} · server {target.server_pid}/{target.server_starttime} "
            f"· pane {target.pane_id}"
        ),
        where=(
            f"herdr socket {target.socket_path!r} server "
            f"{target.server_pid}/{target.server_starttime} pane {target.pane_id}"
        ),
        jump=shlex.join(
            [
                "env",
                "HERDR_ENV=1",
                f"HERDR_SOCKET_PATH={target.socket_path}",
                f"HERDR_PANE_ID={target.pane_id}",
                "herdr",
            ]
        ),
    )


def alert_attention(*, coordinate: str | None, pane: str | None) -> tuple[str, str]:
    """Return the native location and jump used by track-scoped alerts."""
    herdr = herdr_attention(coordinate=coordinate or "")
    if herdr is not None:
        return herdr.where, herdr.jump
    if coordinate:
        return f"tmux session '{coordinate}' pane {pane}", f"tmux switch-client -t {coordinate}"
    return "no live tmux session", ""


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
