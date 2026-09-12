"""The complete Codex compaction sequence, driven through `evaluate`.

The Codex twin of `test_supervisor_compaction_claude`. Same arc, different mechanics
throughout: a `›` composer instead of an empty `❯` box, `Context N% left` instead of
`Ctx: N% left`, a submit confirmed by the pane going BUSY, and a restart that proves
itself by a CHANGED rollout id. That the same latch drives both is the runtime
neutrality this subsystem was ruled to have.
"""

from __future__ import annotations

import contextlib
import io as _io

import registry
import signals
from test_supervisor_builders import FRESH_CODEX_SESSION_ID, WRAPUP_SENTINEL, declare
from test_supervisor_compaction_builders import (
    PREDECESSOR_CODEX_ID,
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


def _latch_under_busy_work(*, repo, topic, session, fake, sup):
    """Stages 1-2: below-threshold busy work, then an in-place recovery."""
    assert _tick(sup=sup, repo=repo, topic=topic).status == "working"
    opened = compaction_record(sup=sup, repo=repo, topic=topic)
    assert opened is not None and opened.session_identity == f"codex:{PREDECESSOR_CODEX_ID}"
    assert opened.watermark_ctx == 45
    assert opened.restart_required is False

    # The recovery under the SAME rollout id. Nothing about the pane says the
    # generation changed; only the rise under an unchanged identity does.
    show_pane(fake=fake, session=session, capture=codex_busy(ctx=88))
    err = _io.StringIO()
    assert _tick(sup=sup, repo=repo, topic=topic, err=err).status == "working"
    latched = compaction_record(sup=sup, repo=repo, topic=topic)
    assert latched is not None and latched.restart_required is True
    assert (latched.from_ctx, latched.to_ctx) == (45, 88)
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")
    assert f"codex:{PREDECESSOR_CODEX_ID}" in err.getvalue()


def _deliver_the_wind_down(*, repo, topic, session, fake, sup):
    """Stages 3-4: 88% is far above the 50% threshold and the wind-down lands anyway."""
    show_pane(fake=fake, session=session, capture=codex_idle(ctx=88, topic=topic))
    view = _tick(sup=sup, repo=repo, topic=topic)
    assert view.status == "warned"
    assert WRAPUP_SENTINEL in "".join(fake.paste_texts())
    assert view.note is not None and "context compaction 45%->88%" in view.note
    stamp = registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert stamp is not None
    assert not fake.has(method="respawn")

    declare(repo=repo, topic=topic, value=signals.STATE_WINDING_DOWN, mtime=1000.0)
    show_pane(fake=fake, session=session, capture=codex_idle(ctx=88, topic=topic))
    pastes = len(fake.paste_texts())
    assert _tick(sup=sup, repo=repo, topic=topic).status == "winding-down"
    assert len(fake.paste_texts()) == pastes
    assert not fake.has(method="respawn")
    return stamp


def test_a_codex_track_latches_a_compaction_and_clears_it_only_on_a_fresh_session(*, tmp_path):
    repo, topic, session, fake, sup = codex_compaction_track(tmp_path=tmp_path, ctx=45)
    _latch_under_busy_work(repo=repo, topic=topic, session=session, fake=fake, sup=sup)
    stamp = _deliver_the_wind_down(repo=repo, topic=topic, session=session, fake=fake, sup=sup)

    # A certifiable `ready` restarts it into a FRESH codex session (never a resume).
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=stamp + 1.0)
    assert _tick(sup=sup, repo=repo, topic=topic).status == "restarting"
    assert fake.has(method="respawn")
    still_owed = compaction_record(sup=sup, repo=repo, topic=topic)
    assert still_owed is not None and still_owed.restart_required is True

    # The successor rollout is adopted: a different id with a replenished window.
    show_pane(fake=fake, session=session, capture=codex_idle(ctx=95, topic=topic))
    cleared = _io.StringIO()
    view = _tick(sup=sup, repo=repo, topic=topic, err=cleared)
    discharged = compaction_record(sup=sup, repo=repo, topic=topic)
    assert discharged is not None and discharged.restart_required is False
    assert discharged.session_identity == f"codex:{FRESH_CODEX_SESSION_ID}"
    assert discharged.watermark_ctx == 95
    assert view.status != "warned"
    assert "context-compaction latch cleared" in cleared.getvalue()
