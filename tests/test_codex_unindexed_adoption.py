"""Live Codex sessions that cannot be adopted must be visible."""

from __future__ import annotations

import codex_sessions
import registry
from test_codex_sessions_fakes import ID_A, ID_B, fake_index, fake_rollout
from test_supervisor_builders import make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_tick_surfaces_unindexed_live_codex_session_in_watched_repo(tmp_path):
    """A live Codex TUI with an open rollout but no index name must not disappear behind
    ``unassigned``. The daemon cannot adopt it to a plan topic, but it can show the
    operator the tmux session whose Codex thread is structurally unadoptable."""
    repo, _topic = make_plan(tmp_path=tmp_path, topic="adoption-gap")
    codex_home = fake_index(tmp_path=tmp_path, records=[(ID_A, "some-other-topic")])
    fake = FakeTmux()
    fake.pane_pids = {7001: "live-codex"}

    def pids(*, comm):
        return [9000] if comm == codex_sessions.CODEX_COMM else []

    def fds(*, pid):
        return [fake_rollout(session_id=ID_B)] if pid == 9000 else []

    def cwd(*, pid):
        return str(repo) if pid == 9000 else None

    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        codex_home=str(codex_home),
        codex_pids_of_comm=pids,
        codex_fd_targets_of=fds,
        codex_cwd_of=cwd,
        ppid_of=lambda *, pid: {9000: 7001}.get(pid),
    )

    views = sup.tick(act=True)

    assert [(row.status, row.tmux, row.runtime) for row in views] == [
        ("unassigned", None, None),
        ("codex-unindexed", "live-codex", "codex"),
    ]
    assert registry.read_mapping(store_path=sup.store_path) == []
    out = sup.out.getvalue()
    assert "NEEDS YOU (1):" in out
    assert f"topic: codex:{ID_B[:8]} | tmux: live-codex (codex) | repo: repo" in out
    assert "no session_index thread_name" in out
