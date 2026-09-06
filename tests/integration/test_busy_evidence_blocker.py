"""Integration-tier scenario: the wrap-up and ready-expiry notice NAME the concrete
busy-evidence blocker that is holding ready-certification.

Regression for overseer-aai2. Observed live 2026-09-06: a track sat in a
`ready` -> expire -> `ready` loop that could never certify, because a live
background shell under the pane held the restart interlock open — and NEITHER
the escalating wrap-up NOR the expiry notice named that blocker, so a session
that sincerely believed it was at a clean stopping point had no signal pointing
at the real obstacle and kept re-declaring `ready`.

The daemon's guarded-paste predicate only ever pastes into an idle, settled,
non-generating pane, so the SOLE busy class that can still be live when either
message lands is a background shell (Claude registry `shell` status, or the
Codex descendant-shell fallback). That is exactly the evidence the message must
name, without weakening the cardinal rule: the daemon still restarts on nothing
but a fresh certifiable `ready`.

Tier: `tests.integration` is one of the documented governed scenario tiers.
"""

from __future__ import annotations

import io as _io

import _supervisor_config

from overseer import registry, signals
from overseer.test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import FakeTmux

MAX_AGE = _supervisor_config.READY_ARM_MAX_AGE

_BLOCKER_PHRASE = "background shell"
_BLOCKER_CALLOUT = "BLOCKING YOUR RESTART"


def _track_with_status(*, tmp_path, clock, status, ctx=40):
    """A discovered, mapped, live plan track idle at `ctx`% with the given Claude status."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    sup.claude_status_by_session = {session: status}
    return repo, topic, session, fake, sup, track


def _notice_texts(*, fake: FakeTmux) -> list[str]:
    return [text for text in fake.paste_texts() if "EXPIRED" in text]


def test_the_low_context_wrapup_names_a_live_background_shell_blocker(*, tmp_path):
    """The FIRST wrap-up, opening the round while a background shell is live, tells the
    session that the shell — not merely 'reach a clean stopping point' — is what stands
    between it and a restart."""
    clock = {"t": 1000.0}
    _repo, _topic, _session, fake, sup, track = _track_with_status(
        tmp_path=tmp_path, clock=clock, status="shell"
    )

    opened = sup.evaluate(track=track, act=True)

    assert opened.status == "warned"
    wrapups = [text for text in fake.paste_texts() if "EXPIRED" not in text]
    assert len(wrapups) == 1
    assert _BLOCKER_PHRASE in wrapups[0]
    assert _BLOCKER_CALLOUT in wrapups[0]


def test_the_expiry_notice_names_a_live_background_shell_blocker(*, tmp_path):
    """The observed loop: a `ready` expires while a background shell holds the interlock
    open, and the expiry notice names the shell so the session can reap it rather than
    re-declaring `ready` into a loop that can never certify."""
    clock = {"t": 1000.0}
    repo, topic, _session, fake, sup, track = _track_with_status(
        tmp_path=tmp_path, clock=clock, status="shell"
    )

    # Open the delivered round.
    assert sup.evaluate(track=track, act=True).status == "warned"

    # Declare ready, age it past the maximum, and let the daemon expire it.
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)
    clock["t"] = 1010.0 + MAX_AGE + 1.0
    sup.evaluate(track=track, act=True)
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY_EXPIRED

    # The next tick sends the one expiry notice.
    clock["t"] += 1.0
    sup.evaluate(track=track, act=True)

    notices = _notice_texts(fake=fake)
    assert len(notices) == 1
    # The blocker is named, without losing the notice's standing content.
    assert _BLOCKER_PHRASE in notices[0]
    assert _BLOCKER_CALLOUT in notices[0]
    assert "A restart requires a fresh ready." in notices[0]
    assert "blocked: <one-line reason>" in notices[0]


def test_no_blocker_callout_when_the_daemon_holds_no_busy_evidence(*, tmp_path):
    """The callout is CONDITIONAL: an idle pane with no background shell gets the
    unchanged wrap-up and expiry notice — the blocker line is never invented."""
    clock = {"t": 1000.0}
    repo, topic, _session, fake, sup, track = _track_with_status(
        tmp_path=tmp_path, clock=clock, status="idle"
    )

    assert sup.evaluate(track=track, act=True).status == "warned"
    wrapups = [text for text in fake.paste_texts() if "EXPIRED" not in text]
    assert len(wrapups) == 1
    assert _BLOCKER_CALLOUT not in wrapups[0]

    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)
    clock["t"] = 1010.0 + MAX_AGE + 1.0
    sup.evaluate(track=track, act=True)
    clock["t"] += 1.0
    sup.evaluate(track=track, act=True)

    notices = _notice_texts(fake=fake)
    assert len(notices) == 1
    assert _BLOCKER_CALLOUT not in notices[0]
