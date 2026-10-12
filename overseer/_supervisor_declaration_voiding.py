"""Activity-based retirement of session declarations the pane has outlived.

This collaborator owns the terminal declaration's narrow exception to persistence:
observed generation can prove that ``done`` no longer describes the session. Merely
running a background command, sitting idle, or aging never does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_state
import registry
import signals
from _supervisor_config import MARKER_VOID_GRACE

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["void_stale_done"]


def void_stale_done(
    *, sup: Supervisor, track: registry.Track, state: signals.TrackState, generating: bool
) -> bool:
    """Return whether a ``done`` declaration still stands after this observation.

    A terminal declaration has no age-based expiry. It is voided only when an acting
    observation proves the session resumed generating after the same tail grace used
    for ``blocked:``, and only when that generation was not caused by a peer injection.
    Replacing the declaration with an inert diagnostic deliberately leaves the round,
    its notified bands, and its certification floor untouched.
    """
    if not generating or _supervisor_state.latest_input_was_peer_injected(sup=sup, track=track):
        return True
    age = sup.now() - state.mtime
    if age <= MARKER_VOID_GRACE:
        return True
    detail = (
        f"session resumed generating after {age:.0f}s; done declaration voided; "
        f"original summary: {state.detail}"
    )
    _ = _supervisor_state.write_state_diagnostic(
        sup=sup,
        track=track,
        token=signals.STATE_DONE_VOIDED,
        detail=detail,
    )
    sup.log(
        message=f"voided done declaration for {track.repo}::{track.topic} "
        f"(age {age:.0f}s > {MARKER_VOID_GRACE:.0f}s grace; session resumed generating)"
    )
    return False
