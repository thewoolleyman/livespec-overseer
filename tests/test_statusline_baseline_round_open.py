"""Round-open re-baselining of the statusline model.

A wrap-up round opening over a live pane must treat the pane's RENDERED model
as authoritative: nothing has been restarted yet, so whatever the session runs
is what operator/enforcement authority left it running. Re-baselining the
stored ``statusline_model`` from that live render is what stops a wrong
inherited baseline from vetoing every restart forever (the wedge measured live
2026-08-29; see plan/statusline-veto-wedge-repair/research/incident-and-fix-shape.md).

The re-baseline is fail-soft: an unreadable rendered statusline at round open
leaves the stored baseline untouched, never silently cleared.
"""

from __future__ import annotations

import contextlib
import io as _io

import registry
import signals
from test_supervisor_builders import (
    TEST_EPIC,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _nul(*, argv: list[str]) -> bytes:
    return b"\0".join(part.encode() for part in argv) + b"\0"


def _row_profile(*, store):
    import json

    rows = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
    return rows[0]["model_profile"]


def test_round_open_rebaselines_a_wrong_inherited_statusline_and_surfaces_once(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    # A permanently-wrong inherited baseline: the launch token is opus-4.8,
    # but the stored statusline display name says "Opus 5" (the internally
    # inconsistent record that vetoed the live incident forever).
    registry.append_mapping(
        track=registry.Track(
            topic=topic,
            repo=str(repo),
            tmux=session,
            epic=TEST_EPIC,
            model_profile={
                "harness": "claude",
                "model": "claude-opus-4-1-20250805",
                "statusline_model": "Opus 5 (1M context)",
                "wrapper": None,
            },
        ),
        store_path=tmp_path / "map.jsonl",
    )
    fake = FakeTmux()
    # The live pane renders "Opus 4.8 (1M context)".
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    fake.pane_pids = {100: session}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid_of=lambda *, pid: {200: 100}.get(pid),
        starttime_of=lambda *, pid: {200: "pt"}.get(pid),
        cmdline_of=lambda *, pid: _nul(
            argv=["claude", "--model=claude-opus-4-1-20250805", "-n", topic]
        )
        if pid == 200
        else None,
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    # The wrong inherited baseline was re-based to the live render at round open.
    assert _row_profile(store=tmp_path / "map.jsonl")["statusline_model"] == "Opus 4.8 (1M context)"
    log = err.getvalue()
    # Surfaced exactly once, naming old -> new.
    assert log.count("statusline baseline re-based at round open") == 1
    assert "Opus 5 (1M context)" in log
    assert "Opus 4.8 (1M context)" in log
    # The launch token itself is unchanged, so this is NOT a launch-profile mismatch.
    assert "launch profile mismatch" not in log


def test_round_open_keeps_statusline_baseline_when_render_is_unreadable(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    registry.append_mapping(
        track=registry.Track(
            topic=topic,
            repo=str(repo),
            tmux=session,
            epic=TEST_EPIC,
            model_profile={
                "harness": "claude",
                "model": "claude-opus-4-1-20250805",
                "statusline_model": "Opus 5 (1M context)",
                "wrapper": None,
            },
        ),
        store_path=tmp_path / "map.jsonl",
    )
    fake = FakeTmux()
    # Ctx is still readable (so a round opens), but the statusline carries no
    # readable model segment: the model re-baseline must fail soft.
    capture = idle_capture(ctx=40).replace(
        "  Opus 4.8 (1M context) | /x/repo | Ctx: 40% left",
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
        cmdline_of=lambda *, pid: _nul(
            argv=["claude", "--model=claude-opus-4-1-20250805", "-n", topic]
        )
        if pid == 200
        else None,
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    # Unreadable render -> the stored baseline is preserved, never cleared.
    assert _row_profile(store=tmp_path / "map.jsonl")["statusline_model"] == "Opus 5 (1M context)"
    assert "statusline baseline re-based at round open" not in err.getvalue()
    assert signals.read_state(repo=str(repo), topic=topic) is None
