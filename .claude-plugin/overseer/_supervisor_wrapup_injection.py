"""Escalating wrap-up injection for restart rounds."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_launch_profile_refresh
import _supervisor_ready
import registry
import signals
from _supervisor_prompts import wrapup_message as _default_wrapup_message
from _supervisor_wrapup_select import select_wrapup_message

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "maybe_inject",
]

wrapup_message_provider = _default_wrapup_message


def armed_bands(*, record: registry.RoundRecord, compaction_latched_at: float | None) -> set[int]:
    """The bands this round counts as notified, as delivery stands RIGHT NOW.

    Ordinarily that is simply what the round recorded. A COMPACTION re-arms them: the
    bands it recorded were delivered to a context generation that has been thrown away
    and summarized, so counting them as notified leaves the wind-down undelivered for
    good — the round already holds its threshold band, and a latched track's band
    selection is floored at that same threshold (`_supervisor_compaction.injection_ctx`),
    so nothing lower is ever due either. That is the whole defect: a healthy-looking
    post-compaction percentage, a standing obligation, and silence.

    The re-arm is bounded to once per LATCH by the round's ``compaction_rearmed_at``,
    which the caller records only after a re-armed delivery actually lands. Nothing is
    cleared from the sidecar here: the round keeps its ``at`` (so the certification
    floor a `ready` must beat does not move) and keeps its recorded bands (so a paste
    that fails to submit is retried rather than being silently forgotten).
    """
    if compaction_latched_at is not None and record.compaction_rearmed_at != compaction_latched_at:
        return set()
    return set(record.bands)


def maybe_inject(  # noqa: PLR0913 — one paste site; the wrap-up needs all of these facts
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    eff_ctx: int,
    threshold: int,
    is_codex: bool = False,
    blocker: str | None = None,
    compaction_latched_at: float | None = None,
) -> None:
    """Escalating, spam-proof wrap-up injection: warn once per crossed band.

    The bands are the effective ``threshold`` plus each lower 10%-band below it
    (40 / 30 / 20 / 10). A band fires at most ONCE per round: the set of
    already-notified bands is DURABLE (the injection-stamp sidecar), so a
    daemon restart never re-spams a band it already sent. Multiple bands crossed
    in one tick coalesce into a SINGLE message but mark ALL of them notified.

    ``target`` is the resolved pane id (RB3). The round's ``at`` stamp is
    written ONLY when OPENING the round (the first band of the round) — a
    re-warn at a lower band does NOT rewrite it, so a ready marker the session
    writes still has ``mtime > at`` and certifies, and re-warns never reset the
    notified bands. On a paste failure that OPENED the round, the just-opened
    round is rolled back (stamp cleared) so the next tick retries cleanly (B5).

    ``is_codex`` selects the runtime-appropriate submit verification — this is the
    change that makes the escalating wrap-up (the daemon's ONLY lever now that
    nothing is force-killed) reach a Codex track, not just a Claude one.

    ``blocker`` names concrete busy evidence the caller observed for this track in the
    same guarded re-read that authorized the paste; when set it is surfaced in the
    wrap-up so the session reaps the real obstacle before declaring ``ready``.

    ``compaction_latched_at`` is the standing context-compaction latch's instant, or
    None for an unlatched track. It RE-ARMS this round's bands exactly once (see
    :func:`armed_bands`) so a compaction inside an already-warned round still reaches
    the session; it authorizes nothing else, and the cardinal rule is untouched.
    """
    repo, topic = track.repo, track.topic
    bands = sorted({threshold} | {b for b in (40, 30, 20, 10) if b < threshold}, reverse=True)
    round_record = registry.read_round_record(repo=repo, topic=topic, stamp_path=sup.stamp_path)
    notified = armed_bands(record=round_record, compaction_latched_at=compaction_latched_at)
    due = [b for b in bands if eff_ctx <= b and b not in notified]
    if not due:
        return
    opened_now = round_record.at is None or round_record.malformed_reason is not None
    state = signals.read_state(repo=repo, topic=topic)
    if (
        opened_now
        and state is not None
        and signals.valid_token(token=state.token)
        and not signals.valid_session_token(token=state.token)
    ):
        due = [threshold]
    if opened_now:
        _supervisor_launch_profile_refresh.refresh_launch_profile_at_wrapup(
            sup=sup,
            track=track,
            target=target,
            capture=sup.tmux.capture_pane(
                session=_supervisor_launch.session_of(sup=sup, track=track)
            ),
        )
        # Stamp BEFORE the paste (design) so a marker the session writes has
        # mtime > at. Only on opening — a re-warn preserves the round's at.
        session = _supervisor_launch.session_of(sup=sup, track=track)
        runtime = "codex" if is_codex else "claude"
        identity = _supervisor_ready.session_identity(
            sup=sup, session=session, topic=topic, runtime=runtime
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
            return
        registry.write_injection_stamp(
            repo=repo,
            topic=topic,
            ts=sup.now(),
            session_identity=identity,
            stamp_path=sup.stamp_path,
        )
    message = select_wrapup_message(
        track=track,
        remaining=eff_ctx,
        worker_wrapup=lambda remaining, repo, topic, epic: wrapup_message_provider(
            remaining=remaining,
            repo=repo,
            topic=topic,
            epic=epic,
            blocker=blocker,
        ),
        blocker=blocker,
    )
    if _supervisor_launch.submit_prompt(
        sup=sup, target=target, text=message, expect_codex=is_codex
    ):
        for b in due:
            registry.add_notified_band(repo=repo, topic=topic, band=b, stamp_path=sup.stamp_path)
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
        sup.log(message=f"injected wrap-up into {repo}::{topic} (ctx {eff_ctx}%, bands {due})")
    else:
        if opened_now:
            # Roll back the just-opened round so the next tick retries cleanly.
            registry.clear_injection_stamp(repo=repo, topic=topic, stamp_path=sup.stamp_path)
        sup.alert(
            repo=repo,
            topic=topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message="wrap-up injection FAILED (paste did not land); will retry",
            condition="wrapup-injection-submit-failed",
        )
