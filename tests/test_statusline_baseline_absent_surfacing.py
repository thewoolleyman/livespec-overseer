"""A profiled track with NO statusline baseline must not be silently unverified.

`restart_blocked_by_statusline_mismatch` used to read the recorded baseline and
`return False` with no alert at all when there was none, so a track carrying a
launch profile but no verification baseline had its recorded model re-asserted
with nothing said about whether that model was ever verified (overseer-ebik5q.2).

The DISTINCTION is what these tests pin, not "some alert fires": a check that
merely asserts an alert exists passes trivially once any alert is added
anywhere. There are THREE shapes at restart and they must stay distinguishable —
baselined-and-agreeing (silence), baselined-but-unread
(`statusline-model-unreadable`), and unbaselined (`statusline-baseline-absent`).
A fourth shape, a row with NO recorded profile at all, is the separate fail-soft
clause and must stay silent; it is pinned below so the new surfacing cannot
widen into it.

The last test is the regression guard: a profile write must never DROP a
`statusline_model` the stored row already carries. Never "drop", not never
"change value" — the round-open re-baseline (a6ce3741) deliberately overwrites
the VALUE from a readable live render, and this guard must not contradict it.
"""

from __future__ import annotations

import contextlib
import io as _io
import json
from dataclasses import replace

import _supervisor_restart
import registry
from test_supervisor_builders import (
    TEST_EPIC,
    arm_ready_marker,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_LAUNCH_MODEL = "claude-opus-4-1-20250805"
# What `idle_capture` renders in its statusline model segment.
_RENDERED = "Opus 4.8 (1M context)"
# Deliberately DIFFERENT from `_RENDERED`, so an assertion that the stored value
# survived a write cannot be satisfied by a value re-read from the pane.
_STORED_BASELINE = "Sonnet 4.6"
_BASELINE_ABSENT = "statusline-baseline-absent"
_UNVERIFIED = "statusline model unverified"
_STATUSLINE_CONDITIONS = frozenset(
    {
        "statusline-model-mismatch",
        "statusline-model-unreadable",
        _BASELINE_ABSENT,
    }
)
# A pane rendering an overlay instead of its statusline: readable pane, no
# readable model segment.
_OVERLAY = (
    "● prior response\n"
    "  1. Type something\n"
    "  2. Chat with Claude\n"
    "  Enter to select · up/down to navigate · Esc to cancel\n"
)


def _nul(*, argv: list[str]) -> bytes:
    return b"\0".join(part.encode() for part in argv) + b"\0"


def _baselined_profile(*, statusline_model: str = _RENDERED) -> dict[str, str | None]:
    return {
        "harness": "claude",
        "model": _LAUNCH_MODEL,
        "statusline_model": statusline_model,
        "wrapper": None,
    }


def _unbaselined_profile() -> dict[str, str | None]:
    # Exactly the three keys `registration_model_profile` emits for a reserved
    # foreman/grooming seat: a launch profile with NO verification baseline.
    return {"harness": "claude", "model": _LAUNCH_MODEL, "wrapper": None}


def _row_profile(*, store):
    rows = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
    return rows[0]["model_profile"]


def _profiled_track(*, tmp_path, capture, profile):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    track = replace(mapped_track(repo=repo, topic=topic, session=session), model_profile=profile)
    registry.append_mapping(track=track, store_path=sup.store_path)
    return repo, topic, fake, sup, track


def _restart_shape(*, tmp_path, capture, profile):
    _repo, _topic, fake, sup, track = _profiled_track(
        tmp_path=tmp_path, capture=capture, profile=profile
    )
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        _supervisor_restart.do_restart(
            sup=sup, track=track, target=fake.pane_id(session=track.tmux)
        )
    conditions = {key[2] for key in sup.alerted} & _STATUSLINE_CONDITIONS
    return conditions, err.getvalue(), fake


def test_the_three_statusline_shapes_stay_distinguishable_at_restart(*, tmp_path):
    agreeing, _agreeing_log, agreeing_fake = _restart_shape(
        tmp_path=tmp_path / "agreeing",
        capture=idle_capture(ctx=30),
        profile=_baselined_profile(),
    )
    unread, unread_log, unread_fake = _restart_shape(
        tmp_path=tmp_path / "unread",
        capture=[_OVERLAY, idle_capture(ctx=30), idle_capture(ctx=30)],
        profile=_baselined_profile(),
    )
    unbaselined, unbaselined_log, unbaselined_fake = _restart_shape(
        tmp_path=tmp_path / "unbaselined",
        capture=idle_capture(ctx=30),
        profile=_unbaselined_profile(),
    )

    # Three shapes, three DISTINCT outcomes. Not "some alert fired".
    assert agreeing == set()
    assert unread == {"statusline-model-unreadable"}
    assert unbaselined == {_BASELINE_ABSENT}
    # None of the three is a veto: every one of them restarts.
    assert agreeing_fake.has(method="respawn")
    assert unread_fake.has(method="respawn")
    assert unbaselined_fake.has(method="respawn")
    # The unbaselined line names the ABSENCE of a baseline. It must never reuse
    # the unreadable line, which reports a recorded-versus-rendered comparison
    # that in this shape never happened — there is no recorded side.
    assert _UNVERIFIED in unbaselined_log
    assert "no recorded statusline verification baseline" in unbaselined_log
    assert _LAUNCH_MODEL in unbaselined_log
    assert "statusline model unreadable" not in unbaselined_log
    assert "statusline model mismatch" not in unbaselined_log
    assert "statusline model unreadable" in unread_log
    assert _UNVERIFIED not in unread_log


def test_a_row_with_no_recorded_profile_at_all_stays_silent(*, tmp_path):
    # The fourth shape, and the boundary the new surfacing must NOT widen into:
    # a row with no `model_profile` re-asserts nothing, so there is nothing
    # unverified to report. It is the separate no-recorded-profile fail-soft
    # clause and is deliberately out of this row's scope.
    conditions, log, fake = _restart_shape(
        tmp_path=tmp_path, capture=idle_capture(ctx=30), profile=None
    )

    assert conditions == set()
    assert _UNVERIFIED not in log
    assert fake.has(method="respawn")


def test_the_baseline_absent_alert_edge_triggers_and_re_arms_when_a_baseline_lands(*, tmp_path):
    repo, topic, fake, sup, track = _profiled_track(
        tmp_path=tmp_path, capture=idle_capture(ctx=30), profile=_unbaselined_profile()
    )
    key = (str(repo), topic, _BASELINE_ABSENT)

    def restart():
        arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
        err = _io.StringIO()
        with contextlib.redirect_stderr(err):
            _supervisor_restart.do_restart(
                sup=sup, track=track, target=fake.pane_id(session=track.tmux)
            )
        return err.getvalue()

    def tick(*, on):
        with contextlib.redirect_stderr(_io.StringIO()):
            _ = sup.evaluate(track=on, act=True)

    assert restart().count(_UNVERIFIED) == 1
    assert key in sup.alerted

    # A tick while the track is STILL unbaselined must not re-arm the alert: the
    # evaluate cascade registers the condition as ACTIVE, so
    # `clear_alert_conditions` retains the key (invariant 10) and the alert stays
    # spent for the rest of the episode.
    tick(on=track)
    assert key in sup.alerted
    assert restart().count(_UNVERIFIED) == 0

    # A baseline lands: the condition goes inactive, the key is dropped, and the
    # alert is re-armed for a later episode.
    tick(on=replace(track, model_profile=_baselined_profile()))
    assert key not in sup.alerted


def test_a_round_open_write_never_drops_a_baseline_the_stored_row_carries(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    # The STORED row carries a baseline ...
    registry.append_mapping(
        track=registry.Track(
            topic=topic,
            repo=str(repo),
            tmux=session,
            epic=TEST_EPIC,
            model_profile=_baselined_profile(statusline_model=_STORED_BASELINE),
        ),
        store_path=tmp_path / "map.jsonl",
    )
    fake = FakeTmux()
    # ... while the render is unreadable, so the refresh resolves no baseline of
    # its own and the write would otherwise carry none.
    capture = idle_capture(ctx=40).replace(
        f"  {_RENDERED} | /x/repo | Ctx: 40% left",
        "  Ctx: 40% left",
    )
    fake.serve(session=session, repo=repo, capture=capture)
    fake.pane_pids = {100: session}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid_of=lambda *, pid: {200: 100}.get(pid),
        starttime_of=lambda *, pid: {200: "pt"}.get(pid),
        cmdline_of=lambda *, pid: _nul(argv=["claude", f"--model={_LAUNCH_MODEL}", "-n", topic])
        if pid == 200
        else None,
    )
    # ... and the in-memory Track carries the KEYLESS birth profile a reserved
    # seat is registered with, which shadows the store on the refresh path.
    track = replace(
        mapped_track(repo=repo, topic=topic, session=session),
        model_profile=_unbaselined_profile(),
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "warned"
    # The write must not DROP the key. `_STORED_BASELINE` is not what the pane
    # renders, so only the stored row can be the source of this value — the
    # round-open re-baseline from a READABLE render is a separate, untouched path.
    assert _row_profile(store=tmp_path / "map.jsonl").get("statusline_model") == _STORED_BASELINE
