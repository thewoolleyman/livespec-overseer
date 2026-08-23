"""Archive-GC full-autonomy retirement edge coverage."""

import json
from pathlib import Path

import registry
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _write_full_autonomy(*, repo, enabled=True):
    (repo / ".livespec.jsonc").write_text(
        '{\n  "livespec-overseer": {\n    "full_autonomy": '
        + ("true" if enabled else "false")
        + "\n  }\n}\n",
        encoding="utf-8",
    )


def _archive_plan(*, repo, topic):
    archived = repo / "plan" / "archive" / topic
    archived.parent.mkdir(parents=True)
    (repo / "plan" / topic).rename(archived)


def test_archive_gc_keeps_row_when_exit_paste_fails(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    _write_full_autonomy(repo=repo)
    _archive_plan(repo=repo, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.paste_ok = False
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    dropped = sup.archive_gc()

    assert dropped == 0
    assert [track.topic for track in registry.read_valid_mapping(store_path=sup.store_path)] == [
        topic
    ]


def test_archive_gc_keeps_row_when_exit_submit_fails(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    _write_full_autonomy(repo=repo)
    _archive_plan(repo=repo, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))

    def reject_enter(*, session, keys):
        assert keys == "Enter"
        return False

    fake.send_keys = reject_enter
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    dropped = sup.archive_gc()

    assert dropped == 0
    assert [track.topic for track in registry.read_valid_mapping(store_path=sup.store_path)] == [
        topic
    ]


def test_archive_gc_drops_archived_full_autonomy_row_without_tmux(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    _write_full_autonomy(repo=repo)
    _archive_plan(repo=repo, topic=topic)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    Path(sup.store_path).write_text(
        json.dumps({"kind": "plan", "repo": str(repo), "topic": topic, "epic": "epic"}) + "\n",
        encoding="utf-8",
    )

    dropped = sup.archive_gc()

    assert dropped == 1
    assert registry.read_valid_mapping(store_path=sup.store_path) == []


def test_archive_gc_keeps_raw_row_without_repo_or_topic(*, tmp_path):
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    Path(sup.store_path).write_text(
        json.dumps({"kind": "plan", "repo": "/repo-only"}) + "\n",
        encoding="utf-8",
    )

    dropped = sup.archive_gc()

    assert dropped == 0


def test_archive_gc_keeps_unknown_kind_row(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    Path(sup.store_path).write_text(
        json.dumps({"kind": "mystery", "repo": str(repo), "topic": topic}) + "\n",
        encoding="utf-8",
    )

    dropped = sup.archive_gc()

    assert dropped == 0


def test_archive_gc_keeps_row_when_repo_root_is_missing(*, tmp_path):
    missing_repo = tmp_path / "missing"
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    Path(sup.store_path).write_text(
        json.dumps({"kind": "plan", "repo": str(missing_repo), "topic": "topic"}) + "\n",
        encoding="utf-8",
    )

    dropped = sup.archive_gc()

    assert dropped == 0


def test_archive_gc_logs_state_cleanup_failure_and_still_retires(*, tmp_path, monkeypatch, capsys):
    repo, topic = make_plan(tmp_path=tmp_path)
    _write_full_autonomy(repo=repo)
    _archive_plan(repo=repo, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )
    state_path = declare(repo=repo, topic=topic, value="winding-down")
    original_unlink = Path.unlink

    def fail_state_unlink(self, *, missing_ok=False):
        if self == state_path:
            raise OSError("synthetic unlink failure")
        return original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_state_unlink)

    dropped = sup.archive_gc()

    assert dropped == 1
    assert "could not clear archived seat state" in capsys.readouterr().err
