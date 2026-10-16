"""_supervisor_nudge — the idle-with-context nudge and the non-responder alert.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. Both surfaces exist for a session that is NOT in trouble the daemon can fix
by restarting it: one keeps an idle session going, the other escalates a session
that has stopped answering as its context runs out. The marker that makes the
keep-going nudge single-shot per idle episode lives in
:mod:`_supervisor_nudge_marker`, because a RELEASED channel hold writes it too and
that release is driven from the reconcile phase rather than from this act.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_channel
import _supervisor_channel_delivery
import _supervisor_channel_hold
import _supervisor_launch
import _supervisor_nudge_marker
import registry
import signals
from _supervisor_prompts import (
    charter_authorized_unblock_nudge_message,
    idle_nudge_message,
    supervisor_idle_nudge_message,
)
from _supervisor_records import InjectState

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "alert_non_responder",
    "nudge_charter_authorized_picker_stall",
    "nudge_idle_with_context",
]


def _deliver_nudge(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    message: str,
    is_codex: bool,
) -> _supervisor_channel_delivery.DeliveryOutcome | None:
    """Deliver the keep-going nudge by its supported channel, else by the paste.

    SPECIFICATION v060, contracts.md, the daemon-message delivery channel: choosing
    the channel changes HOW the nudge is delivered, never WHETHER it is — so the
    caller's marker write is driven by the same "did it land?" answer the paste
    always gave. The whole outcome reaches it rather than that one flag, because
    the contract also makes the caller REPORT the route and say whether the message
    is retried or held, and neither of those is readable from "did it land?".
    ``None`` is the third answer: an act cancelled for this tick, which delivered
    nothing by either path and so has no outcome to report at all.

    The nudge opens no round, so the identity the act targets is the pane's
    currently proven one rather than a round-open identity.
    """
    request = _supervisor_channel_delivery.DeliveryRequest(
        sup=sup,
        track=track,
        target=target,
        text=message,
        kind=_supervisor_channel.NUDGE_MESSAGE,
        is_codex=is_codex,
    )
    channel, cancelled = _supervisor_channel_delivery.resolve_bound_channel(
        request=request,
        identity=_supervisor_channel_delivery.live_identity(
            sup=sup, track=track, is_codex=is_codex
        ),
    )
    if cancelled:
        return None
    return _supervisor_channel_delivery.deliver(request=request, channel=channel)


def nudge_idle_with_context(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    eff_ctx: int,
    threshold: int,
    is_codex: bool = False,
) -> None:
    """Send the single "keep going" nudge to an idle session that still has context
    left, and — only if the delivery lands — write the ``idle-with-context-left``
    marker so it fires at most ONCE per idle episode.

    The inverse of :meth:`_maybe_inject`: it fires ABOVE the threshold to keep a session
    from stopping early, not below it to wind one down. The marker is written AFTER a
    successful delivery (as ``_maybe_inject`` marks its bands only on success), so a
    failed one re-nudges next tick rather than silently marking the episode handled.

    Whichever route carried it is NAMED, on the row and in the daemon log, success or
    failure alike (v060). The contract states that over a daemon message rather than
    over the wrap-up, and an operator reading back a nudge that did not land cannot
    otherwise tell a refused channel from a paste that failed to submit.

    ``is_codex`` selects the runtime-appropriate submit verification (a Codex submit is
    confirmed by the pane going busy, not by a cleared ``❯`` box).

    A HELD channel delivery withholds this nudge entirely (v060). That guard belongs
    here and not only in the wrap-up, and the reason is specific to this act: the
    marker below is written only when a delivery LANDS, so an unconfirmed nudge leaves
    the episode unmarked and the nudge due again on the very next tick — the one shape
    that re-sends a message which may already be sitting in the session's input.
    """
    repo, topic = track.repo, track.topic
    held = _supervisor_channel_hold.held_delivery(sup=sup, track=track)
    if held is not None:
        _supervisor_channel_hold.surface_hold(sup=sup, track=track, hold=held, pane=target)
        return
    if isinstance(track, registry.SupervisorSeat):
        message = supervisor_idle_nudge_message(
            remaining=eff_ctx,
            threshold=threshold,
            repo=repo,
            topic=track.supervised_topic,
            epic=track.epic,
        )
    else:
        message = idle_nudge_message(
            remaining=eff_ctx,
            threshold=threshold,
            repo=repo,
            topic=topic,
            epic=track.epic,
        )
    delivered = _deliver_nudge(
        sup=sup, track=track, target=target, message=message, is_codex=is_codex
    )
    if delivered is None:
        # The act was cancelled for this tick by an unproven channel binding, which
        # `resolve_bound_channel` has already surfaced. Nothing was sent and nothing
        # was pasted, so there is no delivery to report as failed and no marker to
        # write: the episode stays un-nudged and the next observation re-evaluates it.
        return
    path = _supervisor_channel_delivery.record_delivery(
        sup=sup, track=track, record=delivered.record
    )
    if delivered.submitted:
        _supervisor_nudge_marker.write_idle_nudge_state(sup=sup, track=track)
        sup.log(
            message=f"nudged idle-with-context-left {repo}::{topic} "
            f"(ctx {eff_ctx}% > threshold {threshold}%; {path})"
        )
    else:
        _report_undelivered_nudge(sup=sup, track=track, target=target, outcome=delivered, path=path)


def _report_undelivered_nudge(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    outcome: _supervisor_channel_delivery.DeliveryOutcome,
    path: str,
) -> None:
    """Report a nudge that did not land, by the route it took and its disposition.

    The two endings are not the same story and must not read as one. A provable
    non-delivery — a refused channel, a paste that did not submit — is retried on a
    later observation. An UNCONFIRMED channel send may already be sitting in the
    session's input, so it is HELD: never sent again by either path, and withholding
    every later daemon message to that session until it is released. Reporting the
    second as the first told an operator to expect a retry that will never come, and
    named a paste that never happened.
    """
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        pane=target,
        message=(
            f"idle-with-context-left nudge UNCONFIRMED (it may have landed); held, "
            f"and nothing later is delivered to this session until it is released "
            f"({path})"
            if outcome.effect_unknown
            else f"idle-with-context-left nudge FAILED (it did not land); " f"will retry ({path})"
        ),
        condition=(
            "idle-nudge-delivery-unconfirmed"
            if outcome.effect_unknown
            else "idle-nudge-submit-failed"
        ),
    )


def nudge_charter_authorized_picker_stall(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    stall_seconds: int,
    istate: InjectState,
) -> None:
    """Paste a charter reminder into a stalled supervisor picker without submitting it."""
    if istate.picker_stall_nudged:
        return
    message = charter_authorized_unblock_nudge_message()
    if sup.tmux.bracketed_paste(session=target, text=message):
        istate.picker_stall_nudged = True
        echoed = sup.tmux.capture_pane(session=target)
        istate.picker_stall_nudge_echo_capture = echoed or None
        sup.log(
            message=(
                f"nudged charter-authorized picker stall {track.repo}::{track.topic} "
                f"({stall_seconds}s)"
            )
        )
        return
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        pane=target,
        message="charter-authorized picker-stall nudge FAILED (paste did not land)",
        condition="picker-stall-nudge-failed",
    )


def alert_non_responder(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    eff_ctx: int,
    declared: signals.TrackState | None,
) -> None:
    """Report a track deep in the danger band that is not honouring the protocol.

    This is the WHOLE response to such a session: the daemon SAYS SO, loudly, with
    the coordinates to go fix it — and does nothing else. It does NOT restart it
    (maintainer 2026-07-14: "NEVER forcibly restart a session that is not ready; it
    MUST drop the indicator file for action"), because a timer cannot know whether a
    session is safe to kill.

    Two ways to get here, and the report must not conflate them (they need different
    fixes):

    - **declared nothing at all** — the session ignored an escalating wrap-up (once
      per 10% band, insistent from 30%) telling it to ACK immediately. A session bug.
    - **a STALE ``winding-down``** — it DID acknowledge, then never finished; the ACK
      aged out of ``ACK_STALE_AFTER``. It is hung mid-wrap-up, not deaf.

    Either way this is a DEFECT REPORT about that session, not a chore for the
    operator to work around: the fix is to make the session honour the protocol,
    never to have the overseer guess on its behalf.
    """
    repo, topic = track.repo, track.topic
    if declared is not None and declared.token == signals.STATE_WINDING_DOWN:
        age = sup.now() - declared.mtime
        what = (
            f"ACKNOWLEDGED the wrap-up {age:.0f}s ago but never finished "
            f"(stale `{signals.STATE_WINDING_DOWN}`; it is hung mid-wrap-up)"
        )
    else:
        what = (
            f"has declared NOTHING (no {signals.state_path(repo=repo, topic=topic).name}) — "
            f"it is ignoring the wrap-up protocol"
        )
    sup.alert(
        repo=repo,
        topic=topic,
        session=session,
        pane=pane,
        message=(
            f"NOT RESPONDING — ctx {eff_ctx}% left and it {what}. The overseer will "
            f"NOT restart it: only the session may authorize that. A human must act."
        ),
        condition="danger-non-responder",
    )
