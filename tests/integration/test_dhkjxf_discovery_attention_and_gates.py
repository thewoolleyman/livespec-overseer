"""Integration coverage for discovery, adoption, and gate scenarios."""

from __future__ import annotations

import contextlib
import io as _io

import pytest
import registry
import signals
from test_supervisor_builders import declare, idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

from tests.integration.test_parked_delivery_attention import picker_only_capture


@pytest.mark.integration
def test_scenario_collision_derived_worker_name_ending_in_supervisor_is_refused(
    *, tmp_path, capsys
):
    repo_a, _ = make_plan(tmp_path=tmp_path, repo_name="alpha", topic="supervisor")
    repo_b, _ = make_plan(tmp_path=tmp_path, repo_name="beta", topic="supervisor")

    assert registry.discover_plans(watch_repos=[repo_a, repo_b]) == []

    err = capsys.readouterr().err
    assert "alpha-supervisor" in err
    assert "beta-supervisor" in err


@pytest.mark.integration
def test_scenario_reserved_name_live_session_is_not_adopted_as_worker(*, tmp_path):
    from test_supervisor_builders import adopt_sup, write_session

    repo, _topic = make_plan(tmp_path=tmp_path, repo_name="repo-slug", topic="repo-slug-supervisor")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=100, name="repo-slug-supervisor", cwd=repo)
    fake = FakeTmux()
    fake.pane_pids[101] = "supervisor-pane"
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
