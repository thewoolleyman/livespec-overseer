"""Supervisor mapping rows inherit plan-liveness from their worker topic."""

import registry
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _write_full_autonomy(*, repo, enabled):
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


def test_archive_gc_exits_and_retires_archived_full_autonomy_seat(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    _write_full_autonomy(repo=repo, enabled=True)
    _archive_plan(repo=repo, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )
    state_path = declare(repo=repo, topic=topic, value="winding-down")
    supervisor_state_path = write_fresh_supervisor_state(repo=repo, topic=topic)
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        stamp_path=sup.stamp_path,
    )

    dropped = sup.archive_gc()

    assert dropped == 1
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
    assert fake.paste_texts() == ["/exit"]
    assert ("keys", session, "Enter") in fake.calls
    assert not state_path.exists()
    assert not supervisor_state_path.exists()
    assert (
        registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path).at
        is None
    )


def test_archive_gc_does_not_exit_active_same_pane_full_autonomy_seat(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    _write_full_autonomy(repo=repo, enabled=True)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
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
    assert not fake.has(method="paste")


def test_archive_gc_does_not_exit_archived_seat_without_full_autonomy(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    _write_full_autonomy(repo=repo, enabled=False)
    _archive_plan(repo=repo, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    dropped = sup.archive_gc()

    assert dropped == 1
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
    assert not fake.has(method="paste")


def test_archive_gc_leaves_shared_tmux_session_running(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    _write_full_autonomy(repo=repo, enabled=True)
    _archive_plan(repo=repo, topic=topic)
    fake = FakeTmux()
    fake.serve(session="shared-seat", repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session="shared-seat"), store_path=sup.store_path
    )

    dropped = sup.archive_gc()

    assert dropped == 1
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
    assert not fake.has(method="paste")
    assert fake.session_exists(session="shared-seat")


def test_archive_gc_does_not_exit_missing_session(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    _write_full_autonomy(repo=repo, enabled=True)
    _archive_plan(repo=repo, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    dropped = sup.archive_gc()

    assert dropped == 1
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
    assert not fake.has(method="paste")


def test_archived_or_gone_uses_live_worker_plan_for_supervisor_topic(*, tmp_path):
    repo = tmp_path / "repo"
    (repo / "plan" / "worker").mkdir(parents=True)

    assert registry.archived_or_gone(repo=str(repo), topic="worker-supervisor") is False


def test_archive_gc_keeps_supervisor_row_when_worker_plan_is_live(*, tmp_path):
    repo = tmp_path / "repo"
    (repo / "plan" / "worker").mkdir(parents=True)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    registry.append_mapping(
        track=registry.Track(
            topic="worker-supervisor",
            repo=str(repo),
            tmux="worker-supervisor",
            epic="overseer-worker",
        ),
        store_path=sup.store_path,
    )

    dropped = sup.archive_gc()

    assert dropped == 0
    assert [track.topic for track in registry.read_valid_mapping(store_path=sup.store_path)] == [
        "worker-supervisor"
    ]


def test_archive_gc_drops_supervisor_row_when_worker_plan_is_gone(*, tmp_path):
    repo = tmp_path / "repo"
    (repo / "plan").mkdir(parents=True)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    registry.append_mapping(
        track=registry.Track(
            topic="worker-supervisor",
            repo=str(repo),
            tmux="worker-supervisor",
            epic="overseer-worker",
        ),
        store_path=sup.store_path,
    )

    dropped = sup.archive_gc()

    assert dropped == 1
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
