"""The cross-runtime profile recapture when the store cannot take the write.

The heal repairs a mapping ROW, so a track with no row in the store has nothing to
repair. That is not hypothetical: a row can be removed between the tick that read it and
the tick that acts on it, and the recapture must then fall back to the ordinary refusal
rather than reporting a repair that never landed and skipping the restart forever on the
strength of it.
"""

from __future__ import annotations

import contextlib
import io as _io
import json
import sqlite3

import codex_sessions
import registry
import signals
from test_supervisor_builders import (
    TEST_EPIC,
    adopt_sup,
    arm_ready_marker,
    codex_idle_capture,
    make_plan,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

CARRIER_PID = 2914615
PANE_PID = 7001
SESSION_ID = "01a08bff-a75e-75a1-bb61-209e13ac8994"

STALE_CLAUDE_PROFILE: dict[str, str | None] = {
    "harness": "claude",
    "model": "claude-opus-4-8[1m]",
    "statusline_model": "Opus 4.8 (1M context)",
    "wrapper": None,
}


def _codex_home(*, tmp_path, topic, repo):
    home = tmp_path / "codex-home"
    home.mkdir(exist_ok=True)
    (home / "session_index.jsonl").write_text(
        json.dumps({"id": SESSION_ID, "thread_name": topic}) + "\n",
        encoding="utf-8",
    )
    connection = sqlite3.connect(home / "state_1.sqlite")
    with connection:
        _ = connection.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, model TEXT, cwd TEXT)")
        _ = connection.execute(
            "INSERT INTO threads (id, model, cwd) VALUES (?, ?, ?)",
            (SESSION_ID, "gpt-5.6-sol", str(repo)),
        )
    connection.close()
    return home


def _unmapped_codex_track(*, tmp_path):
    """A live bare Codex carrier whose stale-Claude-profiled track is in NO mapping row."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="repo")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    home = _codex_home(tmp_path=tmp_path, topic=topic, repo=repo)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun")
    fake.pane_pids = {PANE_PID: session}
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    rollout = str(
        home / "sessions" / "2026" / "09" / "12" / f"rollout-2026-09-12T05-00-00-{SESSION_ID}.jsonl"
    )
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={CARRIER_PID: PANE_PID},
        starttimes={},
        watch_repos=[str(repo)],
        codex_home=str(home),
        codex_pids_of_comm=lambda *, comm: (
            [CARRIER_PID] if comm == codex_sessions.CODEX_COMM else []
        ),
        codex_fd_targets_of=lambda *, pid: [rollout] if pid == CARRIER_PID else [],
        codex_cwd_of=lambda *, pid: str(repo) if pid == CARRIER_PID else None,
        cmdline_of=lambda *, pid: b"codex\0" if pid == CARRIER_PID else None,
        environ_of=lambda *, pid: b"" if pid == CARRIER_PID else None,
        now=lambda: 1002.0,
        out=_io.StringIO(),
    )
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=CARRIER_PID, name=topic, cwd=str(repo), session_id=SESSION_ID
        )
    }
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=f"codex:{SESSION_ID}",
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    track = registry.Track(
        topic=topic,
        repo=str(repo),
        tmux=session,
        epic=TEST_EPIC,
        model_profile=dict(STALE_CLAUDE_PROFILE),
    )
    return repo, topic, session, fake, sup, track


def test_a_recapture_the_store_cannot_persist_falls_back_to_the_ordinary_refusal(*, tmp_path):
    repo, topic, session, fake, sup, track = _unmapped_codex_track(tmp_path=tmp_path)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup._do_codex_restart(track=track, target=fake.pane_id(session=session))

    assert [call for call in fake.calls if call[0] == "respawn"] == []
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert (str(repo), topic, "stale-launch-profile") in sup.alerted
    assert (str(repo), topic, "launch-profile-self-healed") not in sup.alerted
    assert "cannot relaunch a Codex track" in err.getvalue()
