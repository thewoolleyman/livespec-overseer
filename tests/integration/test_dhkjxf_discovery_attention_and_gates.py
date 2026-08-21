"""Integration coverage for discovery, foreman heartbeat, and gate scenarios."""

from __future__ import annotations

import contextlib
import io as _io
import json
from pathlib import Path

import pytest
import registry
import signals
import supervisor
from test_supervisor_builders import declare, idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

from tests.integration.test_parked_delivery_attention import picker_only_capture


def _heartbeat_path(*, repo: Path) -> Path:
    return repo / "tmp" / "overseer" / "foreman" / "heartbeat.json"


def _write_heartbeat(*, repo, tick_interval_seconds: int = 600) -> None:
    path = _heartbeat_path(repo=repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "written_at": "1970-01-01T00:00:00Z",
                "pid": 1234,
                "tick_generation": 7,
                "tick_interval_seconds": tick_interval_seconds,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _tick_supervisor(*, tmp_path, fake, repo, now: float):
    return make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        own_pane="%7",
        watch_repos=[str(repo)],
        now=lambda: now,
        status_writer=lambda *, path, body: None,
    )


@pytest.mark.integration
def test_scenario_collision_derived_worker_name_ending_in_foreman_is_refused(*, tmp_path, capsys):
    repo_a, _ = make_plan(tmp_path=tmp_path, repo_name="alpha", topic="foreman")
    repo_b, _ = make_plan(tmp_path=tmp_path, repo_name="beta", topic="foreman")

    assert registry.discover_plans(watch_repos=[repo_a, repo_b]) == []

    err = capsys.readouterr().err
    assert "alpha-foreman" in err
    assert "beta-foreman" in err


@pytest.mark.integration
def test_scenario_reserved_name_live_session_is_not_adopted_as_worker(*, tmp_path):
    from test_supervisor_builders import adopt_sup, write_session

    repo, _topic = make_plan(tmp_path=tmp_path, repo_name="repo-slug", topic="repo-slug-foreman")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=100, name="repo-slug-foreman", cwd=repo)
    fake = FakeTmux()
    fake.pane_pids[101] = "foreman-pane"
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={100: 101},
        starttimes={100: "pt"},
        watch_repos=[str(repo)],
    )

    assert sup.build_rows(act=True) == []
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
    assert "NEEDS YOU" not in sup.out.getvalue()


@pytest.mark.integration
def test_scenario_stale_foreman_heartbeat_is_surfaced_as_attention(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    _write_heartbeat(repo=repo)
    fake = FakeTmux()
    sup = _tick_supervisor(tmp_path=tmp_path, fake=fake, repo=repo, now=1801.0)

    rows = sup.tick(act=True)
    output = sup.out.getvalue()

    assert any(row.topic == "foreman" and supervisor.needs_attention(row=row) for row in rows)
    assert "NEEDS YOU (1):" in output
    assert "foreman-heartbeat-stale" in output
    assert not fake.has(method="paste")
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")


@pytest.mark.integration
def test_scenario_absent_foreman_heartbeat_is_silent(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    sup = _tick_supervisor(tmp_path=tmp_path, fake=FakeTmux(), repo=repo, now=4000.0)

    rows = sup.tick(act=True)

    assert all(row.topic != "foreman" for row in rows)
    assert "foreman" not in sup.out.getvalue()
    assert "NEEDS YOU: nothing" in sup.out.getvalue()


@pytest.mark.integration
def test_scenario_bypass_launched_picker_is_structured_gate(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="codex-yolo-picker")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_only_capture(ctx=13))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    view = sup.evaluate(track=track, act=True)

    assert view.status == "blocked:human"
    assert view.picker_open is True
    assert signals.read_state(repo=str(repo), topic=topic) is None
    assert not fake.has(method="paste")
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")


@pytest.mark.integration
def test_scenario_no_structured_surface_may_still_declare_blocked(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="headless-decision")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=13))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    declare(repo=repo, topic=topic, value="blocked: waiting on human")

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "blocked:human"
    assert "waiting on human" in err.getvalue()
    assert not fake.has(method="paste")
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")
