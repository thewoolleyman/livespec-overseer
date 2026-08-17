"""Regression coverage for supervisor-half snapshot registration."""

import contextlib
import io as _io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_snapshot
import registry
import signals
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def picker_capture(*, ctx: int = 80) -> str:
    return (
        "How do you want to ratify?\n"
        "❯ 1. Yes, run /livespec:revise\n"
        "  2. No, ask the operator\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def stamp_name_source(*, sessions_dir: Path, pid: int, name_source: str) -> None:
    path = sessions_dir / f"{pid}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["nameSource"] = name_source
    path.write_text(json.dumps(data), encoding="utf-8")


def supervisor_pair_with_derived_supervisor_name(*, tmp_path: Path, supervisor_capture: str):
    repo, topic = make_plan(tmp_path=tmp_path)
    worker_session = registry.tmux_id(repo=str(repo), topic=topic)
    supervisor_session = signals.supervisor_entity_topic(topic=worker_session)
    fake = FakeTmux()
    fake.serve(session=worker_session, repo=repo, capture=idle_capture(ctx=80))
    fake.serve(session=supervisor_session, repo=repo, capture=supervisor_capture)
    fake.pane_pids[500] = supervisor_session
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(
        sessions_dir=sessions_dir,
        pid=100,
        name="repo-01",
        cwd=str(repo),
        status="idle",
    )
    stamp_name_source(sessions_dir=sessions_dir, pid=100, name_source="derived")
    clock = {"t": 1000.0}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        sessions_dir=sessions_dir,
        ppid_of=lambda *, pid: 500 if pid == 100 else None,
        starttime_of=lambda *, pid: "pt" if pid == 100 else None,
        now=lambda: clock["t"],
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=worker_session),
        store_path=sup.store_path,
        added_at="now",
    )
    write_fresh_supervisor_state(repo=repo, topic=supervisor_session)
    return sup, clock, repo, topic, supervisor_session


def test_daemon_snapshot_tracks_supervisor_half_without_supervisor_mapping_row(*, tmp_path):
    captured = []
    sup, clock, repo, topic, supervisor_session = supervisor_pair_with_derived_supervisor_name(
        tmp_path=tmp_path,
        supervisor_capture=picker_capture(),
    )
    sup.status_snapshot_writer = lambda *, sup, rows: captured.append(
        _supervisor_snapshot.document_payload(sup=sup, rows=rows)
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        first = sup.tick(act=True)
        clock["t"] += 42.0
        second = sup.tick(act=True)

    mapped_topics = {track.topic for track in registry.read_mapping(store_path=sup.store_path)}
    assert mapped_topics == {topic}
    first_rows = {row.topic: row for row in first}
    second_rows = {row.topic: row for row in second}
    assert set(first_rows) >= {topic, supervisor_session}
    assert set(second_rows) >= {topic, supervisor_session}
    supervisor_row = second_rows[supervisor_session]
    assert supervisor_row.tmux == supervisor_session
    assert supervisor_row.status == "blocked:human"
    assert supervisor_row.picker_open is True
    assert supervisor_row.stall_seconds == 42
    snapshot_rows = {
        str(row["topic"]): row
        for row in captured[-1]["rows"]
        if isinstance(row, dict) and isinstance(row.get("topic"), str)
    }
    assert snapshot_rows[supervisor_session]["picker_open"] is True
    assert snapshot_rows[supervisor_session]["stall_seconds"] == 42


def test_absent_supervisor_session_does_not_create_supervisor_snapshot_row(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    worker_session = registry.tmux_id(repo=str(repo), topic=topic)
    supervisor_session = signals.supervisor_entity_topic(topic=worker_session)
    fake = FakeTmux()
    fake.serve(session=worker_session, repo=repo, capture=idle_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=worker_session),
        store_path=sup.store_path,
        added_at="now",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        rows = sup.tick(act=True)

    assert supervisor_session not in {row.topic for row in rows}
