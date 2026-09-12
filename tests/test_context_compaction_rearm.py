"""The ruled contract's second half: a compaction RE-ARMS delivery in the open round.

`test_context_compaction_latch` states the obligation — an in-place compaction is an
exhausted generation, so the cooperative wind-down and the fresh-session restart stay
owed at any later percentage (maintainer ruling 2026-09-12, `overseer-nb7ok7`). This
file states what that obligation is worth when the round is ALREADY OPEN.

A round remembers which escalation bands it has notified, durably and deliberately: a
band fires at most once per round so a daemon bounce cannot re-spam it. A latched track
has its band selection floored at the threshold, because its post-compaction percentage
describes a generation nobody is winding down. Put those two together on a track that
already crossed its threshold NORMALLY — warned at 50%, then drained, then compacted —
and the floored figure selects only bands the round has already recorded: no band is
due, nothing is injected, and the obligation the latch created is never communicated to
the session that owes it.

So a compaction re-arms delivery inside the current round. Once per LATCH, never once
per tick; keeping the round current rather than opening a new one, so the certification
floor a `ready` must beat does not move; and leaving the durable latch exactly where it
was, because a delivery is not a discharge.
"""

from __future__ import annotations

import contextlib
import io as _io

import registry
import signals

from overseer.test_supervisor_compaction_builders import (
    claude_busy,
    claude_compaction_track,
    claude_idle,
    compaction_record,
    show_pane,
    stored_track,
)
from overseer.test_supervisor_render_builders import WRAPUP_SENTINEL

__all__: list[str] = []


def _tick(*, sup, repo, topic):
    with contextlib.redirect_stderr(_io.StringIO()):
        return sup.evaluate(track=stored_track(sup=sup, repo=repo, topic=topic), act=True)


def _round(*, sup, repo, topic):
    return registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


def _warned_then_compacted(*, tmp_path):
    """The measured sequence: a delivered 50% band, a drain to 6%, an in-place recovery."""
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=45))
    assert _tick(sup=sup, repo=repo, topic=topic).status == "warned"
    warned = _round(sup=sup, repo=repo, topic=topic)
    assert warned.bands == [50]
    assert len(fake.paste_texts()) == 1

    # Back to work, down past the danger line, with no further injection window — which
    # is how a session reaches a compaction mid-flight rather than at a safe stop.
    show_pane(fake=fake, session=session, capture=claude_busy(ctx=6))
    assert _tick(sup=sup, repo=repo, topic=topic).status == "working"
    # The in-place recovery, under the SAME live session identity.
    show_pane(fake=fake, session=session, capture=claude_busy(ctx=82))
    assert _tick(sup=sup, repo=repo, topic=topic).status == "working"
    latched = compaction_record(sup=sup, repo=repo, topic=topic)
    assert latched is not None and latched.restart_required is True
    return repo, topic, session, fake, sup, warned


def test_a_same_session_compaction_rearms_the_wind_down_in_the_round_that_already_warned(
    *, tmp_path
):
    repo, topic, session, fake, sup, warned = _warned_then_compacted(tmp_path=tmp_path)

    # The next guarded settled opportunity: the round already holds the 50% band, and
    # the statusline reads a healthy 82%, so no ordinary band is due.
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    view = _tick(sup=sup, repo=repo, topic=topic)

    assert view.status == "warned"
    assert len(fake.paste_texts()) == 2
    assert WRAPUP_SENTINEL in fake.paste_texts()[-1]

    rearmed = _round(sup=sup, repo=repo, topic=topic)
    # The round stays CURRENT: same certification floor, same owning identity, the
    # re-delivered band recorded again rather than a fresh round opened underneath it.
    assert rearmed.at == warned.at
    assert rearmed.session_identity == warned.session_identity
    assert rearmed.bands == [50]
    # The obligation is untouched, and it still buys no act.
    still_owed = compaction_record(sup=sup, repo=repo, topic=topic)
    assert still_owed is not None and still_owed.restart_required is True
    assert not fake.has(method="respawn")
    assert not signals.state_path(repo=str(repo), topic=topic).exists()


def test_the_rearmed_delivery_can_obtain_a_fresh_winding_down_acknowledgement(*, tmp_path):
    repo, topic, session, fake, sup, _warned = _warned_then_compacted(tmp_path=tmp_path)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    _ = _tick(sup=sup, repo=repo, topic=topic)
    assert len(fake.paste_texts()) == 2

    # The point of re-arming is that the ordinary protocol can now run to completion on
    # a track the daemon would otherwise have had no way to reach.
    signals.state_path(repo=str(repo), topic=topic).parent.mkdir(parents=True, exist_ok=True)
    signals.state_path(repo=str(repo), topic=topic).write_text(
        f"{signals.STATE_WINDING_DOWN}\n", encoding="utf-8"
    )
    pastes = len(fake.paste_texts())

    assert _tick(sup=sup, repo=repo, topic=topic).status == "winding-down"
    # A fresh ACK buys patience: never keystroke into a session that is winding down.
    assert len(fake.paste_texts()) == pastes
    assert not fake.has(method="respawn")


def test_an_ordinary_threshold_crossing_still_notifies_each_band_exactly_once(*, tmp_path):
    """THE DISCRIMINATING CONTROL: nothing outside the compaction path re-delivers."""
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=45))
    assert _tick(sup=sup, repo=repo, topic=topic).status == "warned"
    assert len(fake.paste_texts()) == 1

    # A reading that FALLS is ordinary progress inside one generation: the 50% band is
    # already sent and no lower band is due, so this opportunity sends nothing.
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=44))
    view = _tick(sup=sup, repo=repo, topic=topic)

    assert view.status == "warned"
    assert len(fake.paste_texts()) == 1
    record = compaction_record(sup=sup, repo=repo, topic=topic)
    assert record is not None and record.restart_required is False
