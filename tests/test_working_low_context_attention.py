"""Regression tests for report-only attention on busy low-context tracks."""

import contextlib
import io as _io

import pytest
import registry
import signals
from test_supervisor_builders import (
    busy_capture,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_busy_undeclared_track_at_danger_floor_is_reported_without_acting(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=15))
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        own_pane="%7",
        watch_set_path=None,
        watch_repos=[str(repo)],
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="t",
    )

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        for _ in range(3):
            sup.tick(act=True)

    out = sup.out.getvalue()
    surfaced = [ln for ln in err.getvalue().splitlines() if "overseer[SURFACE]" in ln]
    low_context = [ln for ln in surfaced if "working low context" in ln]
    assert "NEEDS YOU (1):" in out
    assert "topic: topic | tmux: topic (claude) | repo: repo" in out
    assert "jump: tmux switch-client -t topic" in out
    assert "working" in out
    assert fake.window_name == "overseer(1!)"
    assert len(low_context) == 1
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")
    assert not fake.has(method="keys")
    assert signals.read_state(repo=str(repo), topic=topic) is None


def test_settled_undeclared_track_at_danger_floor_keeps_threshold_path(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=15))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=track, act=True)

    assert view.status == "danger"
    assert "NOT RESPONDING" in err.getvalue()
    assert fake.has(method="paste")
    assert not fake.has(method="respawn")
