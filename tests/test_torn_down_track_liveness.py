"""`overseer-mkx` — a deliberately torn-down track must not alarm like a lost one.

THE DEFECT, and it is NOT quite the one the item describes. `overseer-mkx` says a
torn-down track renders as *"hung mid-wrap-up"*, citing `_supervisor_nudge.py:145`.
Measured 2026-08-02: it does not. That line documents what a stale `winding-down`
MEANS, but `alert_non_responder` sits deep in the threshold branch and needs a LIVE
managed pane at danger context, so a track whose session is gone never reaches it.

What actually happens is sharper. A worker that declared `winding-down` and was then
killed by supervisor action reports **`session-gone`** — the daemon's ONLY red
status — and keeps reporting it, because discovery keys on the plan DIRECTORY. It is
therefore INDISTINGUISHABLE from a track that died unexpectedly mid-work, which is
the item's real complaint: the maintainer saw a track rendering dead-and-not-working
and had to ask what had happened, 327 minutes after the fact.

THE DISCRIMINATOR IS ALREADY ON DISK AND UNUSED. The track's last declaration says
`winding-down`: the session announced it was wrapping up before it went. A track
that dies while WORKING has no such declaration. So the daemon can already tell an
orderly teardown from an unexpected death, and does not look.

WHAT THIS TRADES, stated plainly rather than hidden: a session that declared
`winding-down` and then genuinely CRASHED now reads as an orderly wind-down. That is
a real loss of distinction, accepted deliberately, because the declaration means the
session had already reached a point it called safe — and the alarm is PRESERVED for
the case that matters most, a track dying mid-work with nothing declared.

WHY THE CONTROLS ARE THE POINT. A fix that simply stops saying `session-gone` is
worse than the defect: that alarm is what the supervision contract rests on. So both
directions are pinned here — a wound-down torn-down track must NOT read red, AND a
track gone with no declaration, or with any other declaration, must STILL read red.
"""

import contextlib
import io as _io

import registry
import signals
from _supervisor_view import ATTENTION_STATUSES
from test_supervisor_builders import declare, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _gone_track_declaring(*, tmp_path, value):
    """A discovered track whose tmux session is GONE, carrying ``value`` on disk."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # no serve() — the session was torn down
    if value is not None:
        declare(repo=repo, topic=topic, value=value, mtime=1.0)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=track, act=True)
    return view


def test_a_wound_down_then_torn_down_track_is_not_reported_as_lost(*, tmp_path):
    """THE RED. It declared the wind-down, then was killed on purpose."""
    view = _gone_track_declaring(tmp_path=tmp_path, value=signals.STATE_WINDING_DOWN)
    assert view.status != "session-gone"
    assert view.status == "wound-down"


def test_a_wound_down_torn_down_track_is_not_in_the_attention_block(*, tmp_path):
    """It is COMPLETE — nothing is wanted, so it must stop occupying `NEEDS YOU`.
    Sitting there red for 327 minutes is the observed cost of the defect."""
    view = _gone_track_declaring(tmp_path=tmp_path, value=signals.STATE_WINDING_DOWN)
    assert view.status not in ATTENTION_STATUSES


def test_a_track_gone_with_no_declaration_still_reports_session_gone(*, tmp_path):
    """THE CONTROL, and the one that matters most: a track that died WHILE WORKING
    declared nothing, so the alarm must survive the fix untouched."""
    view = _gone_track_declaring(tmp_path=tmp_path, value=None)
    assert view.status == "session-gone"
    assert view.status in ATTENTION_STATUSES


def test_a_track_gone_while_blocked_still_reports_session_gone(*, tmp_path):
    """THE SHARPER CONTROL. Only `winding-down` means "I was wrapping up". A track
    that vanished while BLOCKED on a human was not finishing — it was waiting, and
    its disappearance is exactly as alarming as before."""
    view = _gone_track_declaring(tmp_path=tmp_path, value="blocked: waiting on review")
    assert view.status == "session-gone"


def test_a_track_gone_holding_a_ready_declaration_still_reports_session_gone(*, tmp_path):
    """THE THIRD CONTROL. `ready` authorises a RESTART; a track holding one and then
    vanishing is an unfinished round, not a completed teardown."""
    view = _gone_track_declaring(tmp_path=tmp_path, value=signals.STATE_READY)
    assert view.status == "session-gone"
