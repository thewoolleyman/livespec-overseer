"""Repo-level foreman tracked-session tick regressions."""

import contextlib
import io

import foreman_runtime
import registry
import signals
from test_supervisor_builders import (
    TEST_EPIC,
    declare,
    idle_capture,
    make_supervisor,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_tick_evaluates_registered_foreman_track_without_a_plan_directory(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    track = foreman_runtime.register_foreman_track(repo=repo, store_path=sup.store_path)
    _ = registry.record_derived_epic(
        repo=track.repo,
        topic=track.topic,
        epic=TEST_EPIC,
        store_path=sup.store_path,
    )
    fake.serve(session=track.tmux, repo=repo, capture=idle_capture(ctx=40, topic=track.topic))

    with contextlib.redirect_stderr(io.StringIO()):
        views = sup.tick(act=True)

    foreman = next(view for view in views if view.topic == track.topic)
    assert foreman.status == "warned"
    assert not (repo / "plan" / track.topic).exists()
    assert fake.has(method="paste")
    assert "resume foreman ledger epic" in fake.paste_texts()[0]


def test_tick_restarts_registered_foreman_track_only_after_ready(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    track = foreman_runtime.register_foreman_track(repo=repo, store_path=sup.store_path)
    _ = registry.record_derived_epic(
        repo=track.repo,
        topic=track.topic,
        epic=TEST_EPIC,
        store_path=sup.store_path,
    )
    fake.serve(session=track.tmux, repo=repo, capture=idle_capture(ctx=40, topic=track.topic))

    with contextlib.redirect_stderr(io.StringIO()):
        first_views = sup.tick(act=True)
    assert next(view for view in first_views if view.topic == track.topic).status == "warned"
    assert not fake.has(method="respawn")

    declare(repo=repo, topic=track.topic, value=signals.STATE_READY, mtime=1001.0)
    with contextlib.redirect_stderr(io.StringIO()):
        second_views = sup.tick(act=True)

    foreman = next(view for view in second_views if view.topic == track.topic)
    assert foreman.status == "restarting"
    assert fake.has(method="respawn")
