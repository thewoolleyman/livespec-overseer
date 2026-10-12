"""Close a proven Herdr replacement without weakening its durable anti-replay fence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_state
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["complete_replacement_round"]


def complete_replacement_round(*, sup: Supervisor, track: registry.Track) -> str | None:
    """Consume ready only after its diagnostic is durable; otherwise preserve the round."""
    cleared = _supervisor_state.clear_state(
        sup=sup,
        track=track,
        diagnostic_token=signals.STATE_RESTARTED,
        diagnostic_detail="Herdr replacement completed; consumed ready declaration",
        preserve_round_on_failure=True,
    )
    if not cleared:
        return "verified successor is live, but ready declaration cleanup failed"
    sup.log(message=f"completed Herdr replacement for {track.repo}::{track.topic}")
    return None
