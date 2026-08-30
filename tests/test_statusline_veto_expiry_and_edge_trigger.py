"""A standing statusline-mismatch veto must not expire the ready declaration,
and its alert must edge-trigger.

Measured live 2026-08-29: the veto kept a ready declaration and re-alerted EVERY
tick (149 identical lines in one hour), and both kept declarations aged past
READY_ARM_MAX_AGE (30m) and EXPIRED uncollected, stranding an unblocked worker.
The cardinal rule is untouched — the veto still never restarts on a mismatch;
only the expiry bookkeeping and the alert cadence change. See
plan/statusline-veto-wedge-repair/research/incident-and-fix-shape.md.
"""

from __future__ import annotations

import contextlib
import io as _io

import registry
import signals
from _supervisor_config import READY_ARM_MAX_AGE
from test_supervisor_builders import (
    TEST_EPIC,
    arm_ready_marker,
    busy_capture,
    idle_capture,
    make_plan,
    make_supervisor,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_STAMP_TS = 1000.0
_READY_MTIME = 1001.0
_MISMATCH = "statusline model mismatch"


def _nul(*, argv: list[str]) -> bytes:
    return b"\0".join(part.encode() for part in argv) + b"\0"


def _mismatched_profile() -> dict[str, str | None]:
    # Launch token opus-4.8, but the recorded statusline display name says "Opus 5":
    # the pane renders "Opus 4.8 (1M context)", so recorded != rendered -> veto.
    return {
        "harness": "claude",
        "model": "claude-opus-4-1-20250805",
        "statusline_model": "Opus 5 (1M context)",
        "wrapper": None,
    }


def _matching_profile() -> dict[str, str | None]:
    return {
        "harness": "claude",
        "model": "claude-opus-4-1-20250805",
        "statusline_model": "Opus 4.8 (1M context)",
        "wrapper": None,
    }


def _armed_supervisor(*, tmp_path, profile, now, capture):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    registry.append_mapping(
        track=registry.Track(
            topic=topic, repo=str(repo), tmux=session, epic=TEST_EPIC, model_profile=profile
        ),
        store_path=tmp_path / "map.jsonl",
    )
    track = registry.Track(
        topic=topic, repo=str(repo), tmux=session, epic=TEST_EPIC, model_profile=profile
    )
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    fake.pane_pids = {100: session}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        now=now,
        ppid_of=lambda *, pid: {200: 100}.get(pid),
        starttime_of=lambda *, pid: {200: "pt"}.get(pid),
        cmdline_of=lambda *, pid: _nul(
            argv=["claude", "--model=claude-opus-4-1-20250805", "-n", topic]
        )
        if pid == 200
        else None,
    )
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=_STAMP_TS, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=_READY_MTIME)
    return sup, repo, topic, session, fake, track


def test_standing_veto_keeps_an_aged_ready_declaration_unexpired(*, tmp_path):
    # Clock well past the 30-minute max age for the armed declaration.
    now_t = _READY_MTIME + READY_ARM_MAX_AGE + 100.0
    sup, repo, topic, session, fake, track = _armed_supervisor(
        tmp_path=tmp_path,
        profile=_mismatched_profile(),
        now=lambda: now_t,
        capture=idle_capture(ctx=30),
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.evaluate(track=track, act=True)

    # The declaration is NOT silently expired out from under the worker: while the
    # veto holds it survives past the max age (it is surfaced as uncertifiable, the
    # safe outcome, rather than replaced with `ready-expired`).
    assert not fake.has(method="respawn")
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_READY


def test_no_veto_still_expires_an_aged_ready_declaration(*, tmp_path):
    now_t = _READY_MTIME + READY_ARM_MAX_AGE + 100.0
    sup, repo, topic, session, fake, track = _armed_supervisor(
        tmp_path=tmp_path,
        profile=_matching_profile(),  # recorded == rendered -> no disagreement
        now=lambda: now_t,
        capture=idle_capture(ctx=30),
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)

    # With no standing veto the aged declaration expires exactly as before.
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_READY_EXPIRED


def test_veto_blocks_restart_then_consumes_the_ready_once_the_disagreement_clears(*, tmp_path):
    # A YOUNG declaration: the veto blocks the restart while it holds, then the
    # normal restart path consumes it the first tick after the disagreement clears.
    now_t = _READY_MTIME + 5.0
    sup, repo, topic, session, fake, track = _armed_supervisor(
        tmp_path=tmp_path,
        profile=_mismatched_profile(),
        now=lambda: now_t,
        capture=idle_capture(ctx=30),  # renders "Opus 4.8" vs recorded "Opus 5"
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)
    assert view.status == "restarting"
    assert not fake.has(method="respawn")
    assert _MISMATCH in err.getvalue()
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY

    # Disagreement clears (pane now renders the recorded model): restart proceeds.
    fake.serve(
        session=session,
        repo=repo,
        capture=idle_capture(ctx=30).replace("Opus 4.8 (1M context)", "Opus 5 (1M context)"),
    )
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
    assert fake.has(method="respawn")


def test_mismatch_alert_edge_triggers_once_and_re_fires_after_clearing(*, tmp_path):
    now_t = _READY_MTIME + 5.0
    sup, repo, topic, session, fake, track = _armed_supervisor(
        tmp_path=tmp_path,
        profile=_mismatched_profile(),
        now=lambda: now_t,
        capture=idle_capture(ctx=30),
    )

    def tick() -> str:
        err = _io.StringIO()
        with contextlib.redirect_stderr(err):
            sup.evaluate(track=track, act=True)
        return err.getvalue()

    # Two consecutive vetoing ticks emit the mismatch alert exactly ONCE (edge).
    assert tick().count(_MISMATCH) == 1
    assert tick().count(_MISMATCH) == 0

    # The disagreement clears WITHOUT consuming the ready (a busy pane skips the
    # restart branch): the alert re-arms as the veto condition goes inactive.
    fake.serve(
        session=session,
        repo=repo,
        capture=busy_capture(ctx=30).replace("Opus 4.8 (1M context)", "Opus 5 (1M context)"),
    )
    assert tick().count(_MISMATCH) == 0

    # The disagreement recurs: the alert FIRES AGAIN (it was re-armed on clearing).
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    assert tick().count(_MISMATCH) == 1
