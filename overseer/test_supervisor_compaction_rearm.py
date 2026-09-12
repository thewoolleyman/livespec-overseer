"""The post-compaction RE-ARM: a round that already warned must warn again.

`test_supervisor_compaction_claude` drives the arc where the compaction arrives before
any injection window has ever opened, so the round is opened BY the latched delivery
and every band is still due. This file drives the other half, and it is the half that
was broken: the round is ALREADY open and has ALREADY recorded its threshold band when
the compaction happens, so the bands it remembers were delivered to a context
generation that no longer exists. Left alone, the floored post-compaction percentage
selects no band at all, the next safe settled opportunity injects nothing, and the
session is never told to wind the exhausted generation down.

The re-arm is deliberately narrow, and each of these controls pins one edge of it: it
fires once per LATCH rather than once per tick, it keeps the round CURRENT rather than
reopening it (a reopened round would move the certification floor a `ready` has to beat
and reset the notified bands wholesale), it leaves the durable latch standing, and it
never fires for a track that merely crossed its threshold.
"""

from __future__ import annotations

import contextlib
import io as _io

import registry
import signals
from test_supervisor_builders import WRAPUP_SENTINEL
from test_supervisor_compaction_builders import (
    claude_busy,
    claude_compaction_track,
    claude_idle,
    codex_busy,
    codex_compaction_track,
    codex_idle,
    compaction_record,
    show_pane,
    stored_track,
)

__all__: list[str] = []


def _tick(*, sup, repo, topic, err=None):
    sink = err if err is not None else _io.StringIO()
    with contextlib.redirect_stderr(sink):
        return sup.evaluate(track=stored_track(sup=sup, repo=repo, topic=topic), act=True)


def _round(*, sup, repo, topic):
    return registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


def _warn_then_drain_then_compact(*, repo, topic, session, fake, sup, busy):
    """The measured sequence: a delivered 50% band, a drain to 6%, an in-place recovery.

    Returns the round as it stood after the FIRST delivery, which is what the re-armed
    delivery must leave untouched.
    """
    assert _tick(sup=sup, repo=repo, topic=topic).status == "warned"
    warned = _round(sup=sup, repo=repo, topic=topic)
    assert warned.at is not None
    assert warned.bands == [50]
    assert len(fake.paste_texts()) == 1

    # Back to work, and down past the danger line with no injection window ever opening
    # again — which is exactly how a session reaches a compaction mid-flight.
    show_pane(fake=fake, session=session, capture=busy(ctx=6))
    assert _tick(sup=sup, repo=repo, topic=topic).status == "working"

    # The in-place recovery, under the same live session identity.
    show_pane(fake=fake, session=session, capture=busy(ctx=82))
    assert _tick(sup=sup, repo=repo, topic=topic).status == "working"
    latched = compaction_record(sup=sup, repo=repo, topic=topic)
    assert latched is not None and latched.restart_required is True
    assert (latched.from_ctx, latched.to_ctx) == (6, 82)
    assert len(fake.paste_texts()) == 1
    return warned


def test_a_same_session_compaction_rearms_the_wind_down_inside_the_open_round(*, tmp_path):
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=45))
    warned = _warn_then_drain_then_compact(
        repo=repo, topic=topic, session=session, fake=fake, sup=sup, busy=claude_busy
    )

    # The next guarded settled opportunity. The round already holds the 50% band and the
    # pane renders a healthy 82%, so nothing about the ordinary band arithmetic is due —
    # and the session still owes a wind-down of the generation that was thrown away.
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    view = _tick(sup=sup, repo=repo, topic=topic)

    assert view.status == "warned"
    assert len(fake.paste_texts()) == 2
    assert WRAPUP_SENTINEL in fake.paste_texts()[-1]
    assert view.note is not None and "context compaction 6%->82%" in view.note

    rearmed = _round(sup=sup, repo=repo, topic=topic)
    # The round stays CURRENT: same certification floor, same owning identity, and the
    # re-delivered band recorded again rather than a fresh round opened under it.
    assert rearmed.at == warned.at
    assert rearmed.session_identity == warned.session_identity
    assert rearmed.bands == [50]
    # The obligation itself is untouched — the re-arm buys a delivery, not a discharge.
    still_owed = compaction_record(sup=sup, repo=repo, topic=topic)
    assert still_owed is not None and still_owed.restart_required is True
    assert still_owed.latched_at is not None
    # And it buys no act: an undeclared session is reported, never restarted.
    assert not fake.has(method="respawn")
    assert not signals.state_path(repo=str(repo), topic=topic).exists()


def test_the_rearm_fires_once_per_latch_not_once_per_tick(*, tmp_path):
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=45))
    _ = _warn_then_drain_then_compact(
        repo=repo, topic=topic, session=session, fake=fake, sup=sup, busy=claude_busy
    )
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))

    for _ in range(10):
        view = _tick(sup=sup, repo=repo, topic=topic)

    # The latch stands for every one of those ticks. If it re-armed on each of them the
    # daemon would keystroke the same instruction into the same session ten times —
    # which is the spam the per-band bookkeeping exists to prevent.
    assert view.status == "warned"
    assert len(fake.paste_texts()) == 2
    still_owed = compaction_record(sup=sup, repo=repo, topic=topic)
    assert still_owed is not None and still_owed.restart_required is True
    assert not fake.has(method="respawn")


def test_an_unlatched_track_still_warns_its_bands_exactly_once(*, tmp_path):
    """THE DISCRIMINATING CONTROL: nothing outside the compaction path re-delivers."""
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=45))
    assert _tick(sup=sup, repo=repo, topic=topic).status == "warned"
    assert len(fake.paste_texts()) == 1

    # A reading that FALLS is ordinary progress inside one generation: the 50% band was
    # already sent and no lower band is due yet, so this opportunity sends nothing.
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=44))
    view = _tick(sup=sup, repo=repo, topic=topic)

    assert view.status == "warned"
    assert len(fake.paste_texts()) == 1
    record = compaction_record(sup=sup, repo=repo, topic=topic)
    assert record is not None and record.restart_required is False


def test_a_codex_track_rearms_the_same_way(*, tmp_path):
    """The Codex twin: the re-arm lives in the runtime-neutral injection path."""
    repo, topic, session, fake, sup = codex_compaction_track(tmp_path=tmp_path, ctx=45)
    # A Codex submit is confirmed by the pane going BUSY, and the frame it goes busy
    # with is the next reading the fold sees — so it carries the drain, not a rise that
    # would latch the compaction before the drain has happened.
    fake.codex_busy_frame = codex_busy(ctx=6)
    show_pane(fake=fake, session=session, capture=codex_idle(ctx=45, topic=topic))
    warned = _warn_then_drain_then_compact(
        repo=repo, topic=topic, session=session, fake=fake, sup=sup, busy=codex_busy
    )

    show_pane(fake=fake, session=session, capture=codex_idle(ctx=82, topic=topic))
    view = _tick(sup=sup, repo=repo, topic=topic)

    assert view.status == "warned"
    assert len(fake.paste_texts()) == 2
    assert WRAPUP_SENTINEL in fake.paste_texts()[-1]
    rearmed = _round(sup=sup, repo=repo, topic=topic)
    assert rearmed.at == warned.at
    assert rearmed.bands == [50]
    still_owed = compaction_record(sup=sup, repo=repo, topic=topic)
    assert still_owed is not None and still_owed.restart_required is True
    assert not fake.has(method="respawn")
