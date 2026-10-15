"""_supervisor_wrapup_round — what a wrap-up DELIVERY ATTEMPT does to its round.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. :mod:`_supervisor_wrapup_injection` orchestrates one act — which bands are
due, whether the channel binding is proven, the delivery itself — and this module
owns the round-state consequences of however that delivery ended.

The three belong together because they are the round's three reachable ends: it is
STAMPED OPEN before the delivery (so a marker the session writes has
``mtime > at``), its bands are MARKED once a message lands, and it is ROLLED BACK
when the delivery provably did not land. Keeping them beside each other is what
makes the asymmetry between the last two legible: a landed message marks bands, a
provably-failed one un-opens the round, and the may-have-landed middle case does
neither — it keeps the round open, unmarked, for a later retry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_launch_profile_refresh
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "mark_delivered",
    "open_round",
    "report_undelivered",
]


def report_undelivered(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    opened_now: bool,
    effect_unknown: bool,
    path: str,
) -> None:
    """A wrap-up whose submission was not confirmed: un-open ONLY a provable failure.

    SPECIFICATION v059: a paste whose effect is unknown may have landed — the 2026-10-15
    petri wrap-up did, and its session wound down and declared — so its stamped round
    stays open and a ``ready`` answering it certifies. Only a provably failed paste is
    rolled back. Either way the bands stay unmarked, so the delivery is retried.

    v060 generalises the same split to a channel: an UNCONFIRMED send is the channel's
    word for exactly that may-have-landed state, and a pre-transmission refusal is the
    provable failure. ``path`` names the route and its outcome so the log reports a
    failed delivery as specifically as it reports a successful one.
    """
    repo, topic = track.repo, track.topic
    if opened_now and not effect_unknown:
        # Roll back the just-opened round so the next tick retries cleanly.
        registry.clear_injection_stamp(repo=repo, topic=topic, stamp_path=sup.stamp_path)
    sup.alert(
        repo=repo,
        topic=topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        pane=target,
        message=(
            f"wrap-up delivery UNCONFIRMED (it may have landed); round kept open so "
            f"a ready answering it certifies; will retry ({path})"
            if effect_unknown
            else f"wrap-up injection FAILED (it did not land); will retry ({path})"
        ),
        condition=(
            "wrapup-delivery-unconfirmed" if effect_unknown else "wrapup-injection-submit-failed"
        ),
    )


def open_round(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    session: str,
    identity: str | None,
) -> bool:
    """Refresh the launch profile and stamp the round open; False cancels the act.

    Stamp BEFORE the delivery (design) so a marker the session writes has
    ``mtime > at``. Only on opening — a re-warn preserves the round's ``at``.
    """
    repo, topic = track.repo, track.topic
    _supervisor_launch_profile_refresh.refresh_launch_profile_at_wrapup(
        sup=sup,
        track=track,
        target=target,
        capture=sup.tmux.capture_pane(session=session),
    )
    if identity is None:
        sup.alert(
            repo=repo,
            topic=topic,
            session=session,
            pane=target,
            message="wrap-up round NOT opened; session identity could not be determined",
            condition="round-identity-undetermined",
        )
        return False
    registry.write_injection_stamp(
        repo=repo,
        topic=topic,
        ts=sup.now(),
        session_identity=identity,
        stamp_path=sup.stamp_path,
    )
    return True


def mark_delivered(
    *,
    sup: Supervisor,
    track: registry.Track,
    due: list[int],
    eff_ctx: int,
    compaction_latched_at: float | None,
    path: str,
) -> None:
    """Record a landed wrap-up: every band it answered, the latch, and its route."""
    repo, topic = track.repo, track.topic
    for band in due:
        registry.add_notified_band(repo=repo, topic=topic, band=band, stamp_path=sup.stamp_path)
    if compaction_latched_at is not None:
        # Unconditionally, not only when this delivery re-armed anything: a round
        # OPENED by a latched track resets its bands (and this mark with them), so
        # leaving it unwritten there would re-arm again on the very next tick.
        registry.mark_compaction_rearmed(
            repo=repo,
            topic=topic,
            latched_at=compaction_latched_at,
            stamp_path=sup.stamp_path,
        )
    sup.log(message=f"injected wrap-up into {repo}::{topic} (ctx {eff_ctx}%, bands {due}; {path})")
