"""Regression coverage for reserved worker session names."""

import pytest
import registry
from test_supervisor_builders import adopt_sup, make_plan, make_supervisor, write_session
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_daemon_discovery_refuses_collision_derived_supervisor_session_names(*, tmp_path, capsys):
    repo_a, _ = make_plan(tmp_path=tmp_path, repo_name="alpha", topic="supervisor")
    repo_b, _ = make_plan(tmp_path=tmp_path, repo_name="beta", topic="supervisor")
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), extra_repos=[repo_a, repo_b])

    rows = sup.build_rows(act=False)

    assert rows == []
    assert registry.read_mapping(store_path=sup.store_path) == []
    err = capsys.readouterr().err
    assert "alpha-supervisor" in err
    assert "beta-supervisor" in err


def test_tmux_id_refuses_topic_level_foreman_suffix_case_insensitively():
    with pytest.raises(ValueError, match="/data/projects/livespec::Alpha-Foreman"):
        registry.tmux_id(repo="/data/projects/livespec", topic="Alpha-Foreman")


def test_tmux_id_refuses_collision_derived_foreman_suffix():
    with pytest.raises(ValueError, match="livespec-foreman"):
        registry.tmux_id(
            repo="/data/projects/livespec",
            topic="foreman",
            colliding={"foreman"},
        )


def test_discovery_refuses_collision_derived_foreman_session_names(*, tmp_path, capsys):
    repo_a, _ = make_plan(tmp_path=tmp_path, repo_name="alpha", topic="foreman")
    repo_b, _ = make_plan(tmp_path=tmp_path, repo_name="beta", topic="foreman")

    assert registry.discover_plans(watch_repos=[repo_a, repo_b]) == []

    err = capsys.readouterr().err
    assert "alpha-foreman" in err
    assert "beta-foreman" in err


def test_adopt_sessions_refuses_foreman_registry_name_without_attention_alarm(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path, repo_name="repo-slug", topic="repo-slug-foreman")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=100, name="repo-slug-foreman", cwd=repo)
    fake = FakeTmux()
    ppid, starttimes = {100: 101}, {100: "pt"}
    fake.pane_pids[101] = "foreman-pane"
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid=ppid,
        starttimes=starttimes,
        watch_repos=[str(repo)],
    )

    assert sup.build_rows(act=True) == []
    assert registry.read_mapping(store_path=sup.store_path) == []
    assert "NEEDS YOU" not in sup.out.getvalue()
