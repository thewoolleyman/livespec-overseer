"""Process ownership selection for the mixed pane facade."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence

import herdr_identity
import pane_router_coordinates
import terminal_ownership
import terminal_probes
from _seams import PidToOptionalInt

__all__: list[str] = ["current_process_coordinate", "default_herdr_endpoints"]


def default_herdr_endpoints() -> tuple[str, ...]:
    """The standard default Herdr socket plus any explicitly selected instance."""
    return terminal_probes.HerdrOwnershipProbe().endpoints(environ=os.environ)


def current_process_coordinate(
    *,
    process_pid: Callable[[], int],
    process_ppid: PidToOptionalInt,
    probes: Sequence[terminal_ownership.TerminalProbe],
) -> str | None:
    """Exact qualified owner of this process, proven by live ancestry."""
    selected = terminal_ownership.select_owner(
        pid=process_pid(),
        environ=dict(os.environ),
        probes=probes,
        ppid_of=process_ppid,
    )
    claim = selected.claim
    if claim is None or claim.backend not in {
        herdr_identity.HERDR_BACKEND,
        herdr_identity.TMUX_BACKEND,
    }:
        return None
    return pane_router_coordinates.qualified_coordinate(claim=claim)
