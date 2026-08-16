"""_supervisor_state — the round's state-file lifecycle (write, clear, blocked void).

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. The state file is how a tracked session DECLARES itself (`ready`, `blocked`,
an ack). A `ready` declaration arms a restart until idle or max-age expiry; a
`blocked:` declaration may still be retired when active generation proves the session
outlived it. Every helper is fail-soft.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry
import signals
from _supervisor_config import MARKER_VOID_GRACE, track_key

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "clear_state",
    "delete_state_file",
    "void_if_stale",
    "void_stale_blocked",
]


def delete_state_file(*, sup: Supervisor, track: registry.Track) -> bool:
    try:
        signals.state_path(repo=track.repo, topic=track.topic).unlink(missing_ok=True)
    except OSError as exc:
        sup.log(message=f"could not delete state file for {track.repo}::{track.topic}: {exc}")
        return False
    return True


def clear_state(*, sup: Supervisor, track: registry.Track) -> None:
    """Delete a track's state file, clear its stamp, AND reset its inject state.

    Used after a successful restart. ``clear_injection_stamp`` deletes the sidecar key,
    resetting BOTH the round's ``at`` and its notified bands — so after a restart the
    round fully resets and every escalation band can fire again in the next round.
    Clearing on the FILESYSTEM (state file + stamp) makes it durable across a daemon
    restart. It ALSO pops the in-memory ``inject`` state
    (mirroring ``_do_restart``) so the stale ``last_ctx`` does not linger; the
    next threshold crossing opens a clean round that writes a new stamp
    (adversarial code re-review 2026-07-13, blocker RB2).
    """
    _ = delete_state_file(sup=sup, track=track)
    registry.clear_injection_stamp(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
    _ = sup.inject.pop(track_key(repo=track.repo, topic=track.topic), None)


def void_if_stale(
    *, sup: Supervisor, track: registry.Track, ready: bool, resumed_work: bool = True
) -> bool:
    """Compatibility shim: ``ready`` is no longer voided by activity.

    Intervening narration/generation cannot authorize a restart because the restart
    branch still requires a verified settled-idle pane. Staleness is bounded by
    ``READY_ARM_MAX_AGE`` in certification instead.
    """
    _ = sup, track, resumed_work
    return ready


def void_stale_blocked(
    *, sup: Supervisor, track: registry.Track, blocked: str | None, generating: bool
) -> str | None:
    """Void a ``blocked:`` declaration the session has outlived. Returns it, or None.

    A session that is GENERATING is, **by observation, not waiting on a human** — so a
    ``blocked:`` declaration still on disk is provably false. This is NOT the daemon
    making a semantic judgment (invariant 1): it is not guessing that the session is
    unblocked, it is reading that the session is producing tokens, which is
    incompatible with waiting for an answer.

    Why it is needed: nothing else retires a ``blocked:``. ``_clear_state`` runs only
    on the daemon's own restart path, so a pane replaced OUT-OF-BAND (a hand-restarted
    session, a `/clear`) inherits its predecessor's declaration — found live
    2026-07-16, where a fresh session rendered `working (awaiting maintainer next-step
    decision — Codex…)`, a reason written by a session that no longer existed. Left
    alone, the dead reason also fires a false ``blocked:human`` alert the moment the
    session goes idle.

    Two bounds keep it honest, each pinned by a test:

    - **``generating``, not merely ``busy``.** A session busy ONLY via a live
      ``Bash(run_in_background)`` command (Claude ``shell``) is sitting AT ITS PROMPT
      and can legitimately be awaiting a human while a build runs — not provably
      stale, so never voided however old. Only a real generation spinner or Claude
      ``busy`` (actively generating / an in-process sub-agent) qualifies.
    - **The tail grace.** The declaring turn's own final text streams for 10-60s
      AFTER the write, so a young declaration must survive its own busy tail — else
      every legitimate declaration is destroyed before the pane ever goes idle.

    An idle blocked session is never touched: it keeps its declaration and keeps
    alerting, forever, until the session itself retracts it.
    """
    if blocked is None or not generating:
        return blocked
    state = signals.read_state(repo=track.repo, topic=track.topic)
    if state is None or state.token != signals.STATE_BLOCKED:
        return blocked  # unreadable, or no longer a block → leave it
    age = sup.now() - state.mtime
    if age <= MARKER_VOID_GRACE:
        return blocked  # the declaring turn's own tail (RB1)
    _ = delete_state_file(sup=sup, track=track)
    sup.log(
        message=f"voided stale blocked declaration for {track.repo}::{track.topic} "
        f"(age {age:.0f}s > {MARKER_VOID_GRACE:.0f}s grace; session resumed generating)"
    )
    return None
