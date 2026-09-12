"""The complete Claude compaction sequence, driven through `evaluate`.

Deliberately free of Codex statusline text: every capture here is the Claude idle box
and the `Ctx: N% left` statusline, so a reader can see that the latch is driven by the
runtime-neutral detector rather than by anything Codex-shaped. Its Codex twin beside
this file drives the same arc through `Context N% left` and a `›` composer.

The arc is one sequence, staged into helpers only because each stage asserts a
different thing about the same run: stage 1 is the busy work no injection window ever
interrupts, stage 2 the in-place recovery, stage 3 the first safe input opportunity,
stage 4 the ACK, and the test itself owns the declaration and the successor.
"""

from __future__ import annotations

import contextlib
import io as _io

import registry
import signals
from test_supervisor_builders import WRAPUP_SENTINEL, declare
from test_supervisor_compaction_builders import (
    SUCCESSOR_CLAUDE_IDENTITY,
    claude_busy,
    claude_compaction_track,
    claude_idle,
    compaction_record,
    show_pane,
    stored_track,
)

__all__: list[str] = []


def _tick(*, sup, repo, topic, err=None):
    sink = err if err is not None else _io.StringIO()
    with contextlib.redirect_stderr(sink):
        return sup.evaluate(track=stored_track(sup=sup, repo=repo, topic=topic), act=True)


def _latch_under_busy_work(*, repo, topic, session, fake, sup):
    """Stages 1-2: below-threshold busy work, then an in-place recovery."""
    # No idle injection window has ever opened, which is precisely how a session
    # reaches a compaction without having been wound down first.
    assert _tick(sup=sup, repo=repo, topic=topic).status == "working"
    opened = compaction_record(sup=sup, repo=repo, topic=topic)
    assert opened is not None and opened.watermark_ctx == 45
    assert opened.restart_required is False

    # The recovery: still busy, still the same session. The daemon used to read this as
    # health; it must now read it as an exhausted generation.
    show_pane(fake=fake, session=session, capture=claude_busy(ctx=82))
    err = _io.StringIO()
    assert _tick(sup=sup, repo=repo, topic=topic, err=err).status == "working"
    latched = compaction_record(sup=sup, repo=repo, topic=topic)
    assert latched is not None and latched.restart_required is True
    assert (latched.from_ctx, latched.to_ctx) == (45, 82)
    # The cardinal rule is untouched while the pane is busy: no keystroke, no respawn.
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")
    assert "CONTEXT COMPACTION detected" in err.getvalue()


def _deliver_the_wind_down(*, repo, topic, session, fake, sup):
    """Stages 3-4: the wind-down lands above the threshold, then the session ACKs."""
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    view = _tick(sup=sup, repo=repo, topic=topic)
    assert view.status == "warned"
    assert WRAPUP_SENTINEL in "".join(fake.paste_texts())
    assert view.note is not None and "context compaction 45%->82%" in view.note
    # The supervision round is OPEN and stays current: a healthy 82% no longer closes
    # it as recovered.
    stamp = registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert stamp is not None
    assert not fake.has(method="respawn")

    declare(repo=repo, topic=topic, value=signals.STATE_WINDING_DOWN, mtime=1000.0)
    pastes = len(fake.paste_texts())
    assert _tick(sup=sup, repo=repo, topic=topic).status == "winding-down"
    assert len(fake.paste_texts()) == pastes
    assert not fake.has(method="respawn")
    return stamp


def test_a_claude_track_latches_a_compaction_and_clears_it_only_on_a_fresh_session(*, tmp_path):
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    _latch_under_busy_work(repo=repo, topic=topic, session=session, fake=fake, sup=sup)
    stamp = _deliver_the_wind_down(repo=repo, topic=topic, session=session, fake=fake, sup=sup)

    # A certifiable `ready` is the SOLE authorization, exactly as for any track.
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=stamp + 1.0)
    assert _tick(sup=sup, repo=repo, topic=topic).status == "restarting"
    assert fake.has(method="respawn")
    # The obligation is NOT discharged by the respawn itself — only by the successor
    # actually being adopted, which has not happened yet.
    still_owed = compaction_record(sup=sup, repo=repo, topic=topic)
    assert still_owed is not None and still_owed.restart_required is True

    # The successor is adopted: a new session identity with a replenished window.
    sup.claude_identity_by_session[(session, topic)] = SUCCESSOR_CLAUDE_IDENTITY
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=96))
    cleared = _io.StringIO()
    view = _tick(sup=sup, repo=repo, topic=topic, err=cleared)
    discharged = compaction_record(sup=sup, repo=repo, topic=topic)
    assert discharged is not None and discharged.restart_required is False
    assert discharged.session_identity == SUCCESSOR_CLAUDE_IDENTITY
    assert discharged.watermark_ctx == 96
    assert view.status != "warned"
    assert "context-compaction latch cleared" in cleared.getvalue()


def test_a_claude_latch_survives_the_daemon_that_recorded_it(*, tmp_path):
    """The latch is DURABLE: a bounce must not discharge an obligation nobody met."""
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    _latch_under_busy_work(repo=repo, topic=topic, session=session, fake=fake, sup=sup)

    # A fresh daemon generation reads the store and knows nothing else: the in-memory
    # `InjectState` this track accumulated is gone, which is exactly the event an
    # in-memory latch would not survive.
    sup.inject.clear()
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    view = _tick(sup=sup, repo=repo, topic=topic)

    assert view.status == "warned"
    assert WRAPUP_SENTINEL in "".join(fake.paste_texts())
    reloaded = stored_track(sup=sup, repo=repo, topic=topic).context_compaction
    assert reloaded is not None and reloaded.restart_required is True
