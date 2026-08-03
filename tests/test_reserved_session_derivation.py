"""Regression coverage for worker session names reserved for supervisors."""

import registry
from test_supervisor_builders import make_plan, make_supervisor
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
