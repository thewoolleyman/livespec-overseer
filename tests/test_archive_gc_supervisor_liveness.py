"""Supervisor mapping rows inherit plan-liveness from their worker topic."""

import registry
from test_supervisor_builders import make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


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
    assert [track.topic for track in registry.read_mapping(store_path=sup.store_path)] == [
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
    assert registry.read_mapping(store_path=sup.store_path) == []
