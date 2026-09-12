"""Regression tests: completed pane prose must not impersonate the live busy spinner.

Live reproduction 2026-09-12 (`overseer-27bqgt`). The `optimize-console-builds` track
had an empty Claude prompt, Claude registry status `idle`, a current supervision round
and a session-written `ready` — and the daemon still rendered `working` and never
reached the ready restart branch. Running the production parser over the captured pane
isolated the sole match: a COMPLETED assistant sentence reading
`(running gqmtwa.4, as designed)`, which matched the prose-wide `\\(\\s*running\\b`
alternative in `signals._BUSY_ACTIVE_RE`.

That false busy is not the harmless direction the "over-firing busy is SAFE" note
describes. The active-decision `working` branch PRECEDES the settled-idle ready branch,
so the misclassification suppressed the restart until `READY_ARM_MAX_AGE` expired and
rewrote an otherwise valid authorization as `ready-expired`; re-declaring `ready`
reproduced the same hold for as long as the historical prose stayed on screen.

The narrowing is only half the claim. The other half is that REAL busy evidence still
fires, so every control below is written to redden if the alternative was deleted
outright rather than narrowed: `LIVE_HOOK_SPINNER` carries no elapsed marker and no
token counter, so the hook-phase alternative is the ONLY thing that can match it.
"""

from __future__ import annotations

import io as _io

import registry
import signals
from test_supervisor_builders import (
    busy_capture,
    codex_busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

# The completed assistant sentence measured on the stranded pane: ordinary prose about a
# work item, in a response that had already finished streaming.
RUNNING_PROSE = "I left the probe alone (running gqmtwa.4, as designed) and stopped the watcher."

# A live Claude hook phase carrying NO other busy evidence — no `· Ns ·` elapsed, no
# `↓ N tokens` counter — so only the hook-phase alternative can classify it busy.
LIVE_HOOK_SPINNER = "✻ Galloping… (running stop hooks… 1/3)"


def _respawns(*, fake):
    return [call for call in fake.calls if call[0] == "respawn"]


def _open_round(*, tmp_path, ctx=40):
    """Drive a REAL wrap-up round and return everything needed to continue it.

    The round is OPENED rather than seeded, because the stamp the round writes is what a
    later `ready` declaration must post-date. Seeding it with `write_injection_stamp`
    would test the interlock's arithmetic instead of the protocol.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    opened = sup.evaluate(track=track, act=True)

    assert opened.status == "warned"
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is not None
    )
    return repo, topic, session, fake, sup, track


def test_completed_running_prose_is_not_a_live_generation_spinner() -> None:
    """The reproduction, at the parser tier: structurally idle, and classified idle."""
    capture = idle_capture(ctx=32, body=RUNNING_PROSE)

    assert signals.is_busy(capture_text=capture) is False
    assert signals.is_idle_input(capture_text=capture) is True


def test_a_live_claude_hook_phase_is_still_busy() -> None:
    """Control: a real hook phase whose ONLY evidence is the `(running … hooks…)` form."""
    assert signals.is_busy(capture_text=LIVE_HOOK_SPINNER) is True
    assert signals.is_busy(capture_text=busy_capture(ctx=32)) is True


def test_a_live_codex_generation_frame_is_still_busy() -> None:
    """Control: Codex's `esc to interrupt` frame — the signal a Codex submit confirms on."""
    frame = codex_busy_capture(ctx=32)

    assert "esc to interrupt" in frame
    assert signals.is_busy(capture_text=frame) is True
    assert signals.is_codex_idle_input(capture_text=frame) is False


def test_historical_running_prose_no_longer_strands_a_ready_gated_restart(*, tmp_path) -> None:
    """The reproduction, at the supervisor tier: one round, one fresh `ready`, one respawn.

    The successful restart must also CLOSE the predecessor round through the existing
    lifecycle — the declaration is consumed (replaced by the daemon's `restarted`
    diagnostic) and the round's injection stamp is dropped — so the consumed edge cannot
    re-trigger on the next observation.
    """
    repo, topic, session, fake, sup, track = _open_round(tmp_path=tmp_path)
    fake.panes[session] = idle_capture(ctx=40, body=RUNNING_PROSE)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert len(_respawns(fake=fake)) == 1
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )

    sup.evaluate(track=track, act=True)  # the consumed declaration must not fire again
    assert len(_respawns(fake=fake)) == 1


def test_a_genuinely_busy_pane_carrying_a_fresh_ready_is_never_respawned(*, tmp_path) -> None:
    """Safety control: narrowing the parser must not weaken the busy interlock."""
    repo, topic, session, fake, sup, track = _open_round(tmp_path=tmp_path)
    fake.panes[session] = busy_capture(ctx=40)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    view = sup.evaluate(track=track, act=True)

    assert view.status == "working"
    assert _respawns(fake=fake) == []
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY


def test_an_undeclared_idle_pane_with_running_prose_is_never_respawned(*, tmp_path) -> None:
    """Safety control: the cardinal rule is unchanged — idle is not an authorization."""
    repo, topic, session, fake, sup, track = _open_round(tmp_path=tmp_path)
    fake.panes[session] = idle_capture(ctx=40, body=RUNNING_PROSE)

    view = sup.evaluate(track=track, act=True)

    assert view.status != "restarting"
    assert _respawns(fake=fake) == []
    assert signals.read_state(repo=str(repo), topic=topic) is None
