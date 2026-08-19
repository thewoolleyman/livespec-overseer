"""Regression coverage for ``supervisor.py start`` slow-boot reporting."""

import _registry_core
import registry
import supervisor
from test_supervisor_builders import isolate_store, make_plan
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_cli_start_maps_a_live_launch_whose_resume_submission_is_unverified(
    *, tmp_path, monkeypatch, capsys
):
    """A slow first boot can leave submit verification inconclusive after launch.

    That is not the same fact as a failed launch: once the exact tmux session is a live
    Claude pane, ``start`` must publish the mapping row so daemon supervision can recover
    the pending resume instead of leaving an unmapped live worker behind.
    """
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    stamp = tmp_path / "stamps.json"
    monkeypatch.setattr(_registry_core, "DEFAULT_STAMP_PATH", stamp)
    fake = FakeTmux()
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 0

    out = capsys.readouterr().out
    assert f"launched-unverified {repo}::{topic}" in out
    assert f"tmux session {session}" in out
    rows = registry.read_valid_mapping(store_path=store)
    assert [(row.repo, row.topic, row.tmux) for row in rows] == [(str(repo), topic, session)]
    assert registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=stamp) is True
