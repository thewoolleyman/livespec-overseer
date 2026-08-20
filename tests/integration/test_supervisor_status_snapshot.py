"""Integration tests for the per-tick status snapshot export."""

from __future__ import annotations

import importlib
import io as _io
import json
from pathlib import Path

import pytest

from overseer import claude_sessions, codex_sessions, registry, supervisor
from overseer.test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_session,
)
from overseer.test_supervisor_fakes import FakeTmux

OVERSEER_DIR = Path(__file__).resolve().parents[2] / "overseer"

__all__: list[str] = []


def snapshot_module():
    module_path = OVERSEER_DIR / "_supervisor_snapshot.py"
    assert module_path.is_file()
    return importlib.import_module("_supervisor_snapshot")


def test_only_canonical_snapshot_writer_module_exists():
    assert (OVERSEER_DIR / "_supervisor_snapshot.py").is_file()
    assert not (OVERSEER_DIR / "_supervisor_status_snapshot.py").exists()


def make_live_mapped_supervisor(
    *,
    tmp_path,
    repo,
    topic,
    status_path,
    status_writer=None,
    ctx=73,
):
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake.pane_pids = {50: session}
    write_session(
        sessions_dir=sessions_dir,
        pid=101,
        name=topic,
        cwd=repo,
        proc_start="12345",
        status="idle",
    )
    kwargs = {}
    if status_writer is not None:
        kwargs["status_writer"] = status_writer
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        status_path=status_path,
        watch_repos=[str(repo)],
        sessions_dir=str(sessions_dir),
        ppid_of=lambda *, pid: {101: 50, 50: 1}.get(pid),
        starttime_of=lambda *, pid: {101: "12345"}.get(pid),
        **kwargs,
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="2026-08-03T00:00:00Z",
    )
    return sup, session


def test_tick_writes_round_trippable_status_snapshot(*, tmp_path):
    module = snapshot_module()
    repo, topic = make_plan(tmp_path=tmp_path)
    status_path = tmp_path / "status.json"
    sup, session = make_live_mapped_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        topic=topic,
        status_path=status_path,
        ctx=73,
    )

    rows = sup.tick(act=True)
    read = module.read_status_snapshot(path=status_path)

    assert read is not None
    assert read.generation == 1
    assert read.mtime > 0
    assert read.document["schema_version"] == module.SCHEMA_VERSION
    assert read.document["daemon_instance_id"] == sup.daemon_instance_id
    assert read.document["tick_generation"] == 1
    assert isinstance(read.document["written_at"], str)
    assert len(read.document["rows"]) == len(rows)
    row = read.document["rows"][0]
    assert row == {
        "topic": topic,
        "repo": str(repo),
        "tmux": session,
        "runtime": "claude",
        "status": "idle-with-context-left",
        "note": None,
        "ctx": 73,
        "progress_now": False,
        "human_wait": False,
        "picker_open": False,
        "stall_seconds": 0,
        "supervisor_state_stale": False,
        "round_open": False,
        "acked": False,
        "session_identity": "claude:101:12345:topic",
    }
    assert json.loads(status_path.read_text(encoding="utf-8")) == read.document


def test_snapshot_reports_daemon_package_provenance(*, tmp_path):
    module = snapshot_module()
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    document = module.document_payload(sup=sup, rows=[])

    assert document["daemon_package"] == {
        "package_dir": str(OVERSEER_DIR),
        "version": supervisor.APP_VERSION,
    }


def test_snapshot_note_is_elided_at_serialization(*, tmp_path):
    module = snapshot_module()
    repo, topic = make_plan(tmp_path=tmp_path)
    blocked_reason = "blocked: " + "sensitive detail " * 80
    declare(repo=repo, topic=topic, value=blocked_reason)
    status_path = tmp_path / "status.json"
    sup, _session = make_live_mapped_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        topic=topic,
        status_path=status_path,
        ctx=72,
    )

    sup.tick(act=True)
    read = module.read_status_snapshot(path=status_path)

    assert read is not None
    row = read.document["rows"][0]
    assert isinstance(row["note"], str)
    assert len(row["note"]) <= module.SNAPSHOT_NOTE_LIMIT
    assert row["note"].endswith("...")
    assert "sensitive detail sensitive detail sensitive detail sensitive detail" not in (
        status_path.read_text(encoding="utf-8")
    )


def test_snapshot_writer_failure_is_contained_and_edge_reported(*, tmp_path, capsys):
    _module = snapshot_module()
    repo, topic = make_plan(tmp_path=tmp_path)

    def raising_writer(*, path, body):
        raise OSError(f"cannot write {path}")

    sup, _session = make_live_mapped_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        topic=topic,
        status_path=tmp_path / "status.json",
        status_writer=raising_writer,
        ctx=74,
    )

    rows = sup.tick(act=True)
    _ = sup.tick(act=True)
    err = capsys.readouterr().err

    assert rows[0].status == "idle-with-context-left"
    assert sup.tick_generation == 2
    assert err.count("status snapshot write failed") == 1
    assert "cannot write" in err


def test_tick_invokes_status_snapshot_writer_once_per_completed_tick(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    calls = []

    def recording_writer(*, sup, rows):
        calls.append((sup.tick_generation, rows))

    sup, _session = make_live_mapped_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        topic=topic,
        status_path=tmp_path / "status.json",
        ctx=75,
    )
    sup.status_snapshot_writer = recording_writer

    rows = sup.tick(act=True)

    assert calls == [(1, rows)]


def test_legacy_status_snapshot_path_still_selects_snapshot_target(*, tmp_path):
    module = snapshot_module()
    repo, topic = make_plan(tmp_path=tmp_path)
    status_path = tmp_path / "status.json"
    sup, _session = make_live_mapped_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        topic=topic,
        status_path=None,
        ctx=76,
    )
    sup.status_snapshot_path = status_path

    sup.tick(act=True)

    read = module.read_status_snapshot(path=status_path)
    assert read is not None
    assert read.generation == 1


def test_default_status_snapshot_path_is_selectable_without_writing_home(*, tmp_path):
    module = snapshot_module()
    repo, topic = make_plan(tmp_path=tmp_path)
    writes = []

    def recording_writer(*, path, body):
        writes.append((path, body))

    sup, _session = make_live_mapped_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        topic=topic,
        status_path=None,
        status_writer=recording_writer,
        ctx=76,
    )

    sup.tick(act=True)

    assert [write[0] for write in writes] == [module.DEFAULT_STATUS_PATH]
    assert json.loads(writes[0][1])["tick_generation"] == 1


def test_snapshot_atomic_write_raise_mode_reports_write_failures(*, tmp_path, monkeypatch):
    registry_core = importlib.import_module("_registry_core")

    def raising_mkstemp(*, dir, prefix, suffix):
        raise OSError("no space")

    monkeypatch.setattr(registry_core.tempfile, "mkstemp", raising_mkstemp)

    with pytest.raises(OSError, match="no space"):
        registry.atomic_write(path=tmp_path / "status.json", body="{}", raise_errors=True)


def test_snapshot_reader_exposes_generation_and_mtime_for_staleness_detection(*, tmp_path):
    module = snapshot_module()
    repo, topic = make_plan(tmp_path=tmp_path)
    status_path = tmp_path / "status.json"
    sup, _session = make_live_mapped_supervisor(
        tmp_path=tmp_path,
        repo=repo,
        topic=topic,
        status_path=status_path,
        ctx=75,
    )

    sup.tick(act=True)
    first = module.read_status_snapshot(path=status_path)
    sup.tick(act=True)
    second = module.read_status_snapshot(path=status_path)

    assert first is not None
    assert second is not None
    assert module.snapshot_unchanged(previous=first.freshness, current=first.freshness)
    assert not module.snapshot_unchanged(previous=first.freshness, current=second.freshness)
    assert second.generation == first.generation + 1


def test_snapshot_reader_fails_closed_for_unreadable_unknown_or_newer_schema(*, tmp_path):
    module = snapshot_module()
    missing = tmp_path / "missing.json"
    malformed = tmp_path / "malformed.json"
    unknown_schema = tmp_path / "unknown.json"
    newer_schema = tmp_path / "newer.json"
    bad_generation = tmp_path / "bad-generation.json"
    bool_generation = tmp_path / "bool-generation.json"
    malformed.write_text("not json", encoding="utf-8")
    unknown_schema.write_text('{"schema_version": 0, "tick_generation": 1}', encoding="utf-8")
    newer_schema.write_text('{"schema_version": 2, "tick_generation": 1}', encoding="utf-8")
    bad_generation.write_text('{"schema_version": 1, "tick_generation": "1"}', encoding="utf-8")
    bool_generation.write_text('{"schema_version": 1, "tick_generation": true}', encoding="utf-8")

    assert module.read_status_snapshot(path=missing) is None
    assert module.read_status_snapshot(path=malformed) is None
    assert module.read_status_snapshot(path=unknown_schema) is None
    assert module.read_status_snapshot(path=newer_schema) is None
    assert module.read_status_snapshot(path=bad_generation) is None
    assert module.read_status_snapshot(path=bool_generation) is None


def test_cli_list_json_uses_snapshot_serializer_without_table_or_ansi(
    *, tmp_path, monkeypatch, capsys
):
    """`list --json` is the foreman's observation-only fallback: same row serializer as
    the daemon snapshot, but no human table render and no ANSI terminal decoration."""
    module = snapshot_module()
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="2026-08-03T00:00:00Z",
    )
    expected = module.document_payload(sup=sup, rows=sup.tick(act=False))
    sup.out = _io.StringIO()
    monkeypatch.setattr(supervisor, "build_supervisor", lambda: sup)

    assert supervisor.main(argv=["list", "--json"]) == 0
    captured = capsys.readouterr()
    document = json.loads(captured.out)

    assert document == expected
    assert captured.err == ""
    assert "Topic" not in captured.out
    assert "\x1b[" not in captured.out
    assert sup.out.getvalue() == ""


def test_snapshot_session_identity_covers_runtime_and_absent_session_cases(*, tmp_path):
    module = snapshot_module()
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    sup.claude_identity_by_session = {
        ("claude-pane", "topic"): "claude:11:222:topic",
    }
    sup.live_codex = {
        ("codex-pane", "topic"): codex_sessions.CodexSession(
            pid=10, name="topic", cwd="/repo", session_id="codex-session"
        )
    }

    claude_row = supervisor.RowView(
        topic="topic",
        repo="/repo",
        tmux="claude-pane",
        ctx=None,
        status="working",
        runtime="claude",
    )
    codex_row = supervisor.RowView(
        topic="topic", repo="/repo", tmux="codex-pane", ctx=None, status="working", runtime="codex"
    )
    absent_row = supervisor.RowView(
        topic="unassigned", repo="/repo", tmux=None, ctx=None, status="unassigned"
    )
    fallback_row = supervisor.RowView(
        topic="topic", repo="/repo", tmux="tmux-pane", ctx=None, status="working"
    )

    assert module.row_payload(sup=sup, row=claude_row)["session_identity"] == (
        "claude:11:222:topic"
    )
    assert module.row_payload(sup=sup, row=codex_row)["session_identity"] == "codex:codex-session"
    assert module.row_payload(sup=sup, row=absent_row)["session_identity"] == (
        "none:/repo:unassigned"
    )
    assert (
        module.row_payload(sup=sup, row=fallback_row)["session_identity"] == "tmux:tmux-pane:topic"
    )


def test_claude_session_api_exports_topic_scoped_identity_join(*, tmp_path):
    session = "topic"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(
        sessions_dir=sessions_dir,
        pid=101,
        name="topic",
        cwd=tmp_path / "repo",
        proc_start="12345",
        status="idle",
    )

    identities = claude_sessions.identities_by_tmux_session(
        sessions_dir=sessions_dir,
        pane_pid_to_session={50: session},
        ppid_of=lambda *, pid: {101: 50, 50: 1}.get(pid),
        starttime_of=lambda *, pid: {101: "12345"}.get(pid),
    )

    assert identities == {(session, "topic"): "claude:101:12345:topic"}
