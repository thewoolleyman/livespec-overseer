import json

import _registry_core
import codex_sessions
import pytest
import registry
import supervisor
from test_supervisor_builders import idle_capture, make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_tick_writes_status_snapshot_schema(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=72))
    path = tmp_path / "status.json"
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        status_snapshot_path=path,
        watch_repos=[str(repo)],
        sessions_dir=str(tmp_path / "sessions"),
    )

    views = sup.tick(act=True)

    assert path.is_file()
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert snapshot == {
        "schema_version": 1,
        "daemon_instance_id": sup.daemon_instance_id,
        "tick_generation": 1,
        "written_at": "1970-01-01T00:16:40Z",
        "rows": [
            {
                "topic": topic,
                "repo": str(repo),
                "tmux": session,
                "runtime": "claude",
                "status": views[0].status,
                "note": None,
                "ctx": 72,
                "progress_now": False,
                "human_wait": False,
                "round_open": False,
                "acked": False,
                "session_identity": f"claude:{session}:{topic}",
            }
        ],
    }


def test_status_snapshot_note_is_flattened_and_bounded(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    path = tmp_path / "status.json"
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), status_snapshot_path=path)
    long_note = "blocked reason line one\n" + ("session text " * 30)

    sup.status_snapshot_writer(
        sup=sup,
        rows=[
            _snapshot_row(
                repo=str(repo),
                topic=topic,
                session=session,
                note=long_note,
            )
        ],
    )

    note = json.loads(path.read_text(encoding="utf-8"))["rows"][0]["note"]
    assert isinstance(note, str)
    assert "\n" not in note
    assert len(note) <= 80
    assert note.endswith("...")
    assert "session text session text session text session text session text" not in note


def test_status_snapshot_writer_failure_is_contained_and_edge_reported(*, tmp_path, monkeypatch):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=72))
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        sessions_dir=str(tmp_path / "sessions"),
    )
    calls = {"count": 0}
    surfaced: list[str] = []

    def raising_writer(*, sup, rows):
        calls["count"] += 1
        raise OSError("disk full")

    def ignore_track_alert(*, repo, topic, session, pane, message, condition="default"):
        return None

    monkeypatch.setattr(sup, "alert", ignore_track_alert)
    monkeypatch.setattr(sup, "status_snapshot_writer", raising_writer)
    monkeypatch.setattr(sup, "surface", lambda *, message: surfaced.append(message))

    views = sup.tick(act=True)
    views_again = sup.tick(act=True)

    assert len(views) == 1
    assert len(views_again) == 1
    assert calls["count"] == 2
    assert surfaced == ["status snapshot write failed: disk full"]


def test_status_snapshot_generation_and_mtime_expose_staleness(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=72))
    path = tmp_path / "status.json"
    clock = {"now": 1000.0}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        status_snapshot_path=path,
        now=lambda: clock["now"],
        watch_repos=[str(repo)],
        sessions_dir=str(tmp_path / "sessions"),
    )

    sup.tick(act=True)
    first = json.loads(path.read_text(encoding="utf-8"))
    first_mtime = path.stat().st_mtime_ns
    clock["now"] = 1011.0
    sup.tick(act=True)
    second = json.loads(path.read_text(encoding="utf-8"))
    second_mtime = path.stat().st_mtime_ns

    assert (first["tick_generation"], second["tick_generation"]) == (1, 2)
    assert second_mtime > first_mtime


def test_status_snapshot_serializes_live_codex_session_identity(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    path = tmp_path / "status.json"
    session_id = "019f548d-0000-4000-8000-000000000000"
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), status_snapshot_path=path)
    sup.live_codex[(session, topic)] = codex_sessions.CodexSession(
        pid=123,
        name=topic,
        cwd=str(repo),
        session_id=session_id,
    )

    sup.status_snapshot_writer(
        sup=sup,
        rows=[
            supervisor.RowView(
                topic=topic,
                repo=str(repo),
                tmux=session,
                runtime="codex",
                ctx=91,
                status="idle",
            )
        ],
    )

    row = json.loads(path.read_text(encoding="utf-8"))["rows"][0]
    assert row["session_identity"] == f"codex:{session_id}"


def test_snapshot_atomic_write_raise_mode_reports_write_failures(*, tmp_path, monkeypatch):
    def raising_mkstemp(*, dir, prefix, suffix):
        raise OSError("no space")

    monkeypatch.setattr(_registry_core.tempfile, "mkstemp", raising_mkstemp)

    with pytest.raises(OSError, match="no space"):
        _registry_core.atomic_write(path=tmp_path / "status.json", body="{}", raise_errors=True)


def _snapshot_row(*, repo: str, topic: str, session: str, note: str):
    return supervisor.RowView(
        topic=topic,
        repo=repo,
        tmux=session,
        runtime="claude",
        ctx=12,
        status="blocked:human",
        note=note,
        human_wait=True,
    )
