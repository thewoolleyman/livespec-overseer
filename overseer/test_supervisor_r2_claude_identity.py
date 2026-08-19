"""Beside-tests for supervisor.py — r2 claude identity.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io
import os

import pytest
import registry
from test_supervisor_builders import (
    adopt_sup,
    make_plan,
    mapped_track,
    write_session,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_stale_tmux_mapping_is_repointed_when_topic_session_moves(*, tmp_path):
    """When a topic's live named session resolves to a DIFFERENT tmux session than the store
    records (a generic window reused for another topic; the session moved), adoption
    RE-POINTS the mapping to the current tmux within one tick rather than freezing the stale
    binding. The re-pointed store then drives acts at the RIGHT pane."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="alpha")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()
    ppid: dict[int, int] = {}
    starttimes: dict[int, str] = {}
    # A live named session for `alpha` whose pid walks up to tmux session `new-tmux`.
    write_session(sessions_dir=sessions_dir, pid=100, name="alpha", cwd=str(repo))
    starttimes[100] = "pt"
    shell = 101
    ppid[100] = shell
    fake.pane_pids[shell] = "new-tmux"
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid=ppid,
        starttimes=starttimes,
        watch_repos=[str(repo)],
    )
    # The store maps `alpha` to a STALE tmux session (`old-tmux`) — where it used to run.
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session="old-tmux"),
        store_path=sup.store_path,
        added_at="pre",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.adopt_sessions()

    rows = {
        (r.repo, r.topic): r.tmux for r in registry.read_valid_mapping(store_path=sup.store_path)
    }
    assert (
        rows[(os.path.normpath(str(repo)), "alpha")] == "new-tmux"
    )  # re-pointed to the live session


def test_repoint_is_idempotent_when_the_mapping_already_matches(*, tmp_path):
    """A steady-state tick where the live session's tmux already equals the stored mapping
    must NOT rewrite the store (no churn) and must NOT re-adopt (no duplicate row)."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="alpha")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()
    write_session(sessions_dir=sessions_dir, pid=100, name="alpha", cwd=str(repo))
    ppid = {100: 101}
    fake.pane_pids[101] = "the-tmux"
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid=ppid,
        starttimes={100: "pt"},
        watch_repos=[str(repo)],
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session="the-tmux"),
        store_path=sup.store_path,
        added_at="pre",
    )

    assert (
        registry.repoint_tmux(
            repo=str(repo), topic=topic, new_tmux="the-tmux", store_path=sup.store_path
        )
        is False
    )  # no-op
    with contextlib.redirect_stderr(_io.StringIO()):
        adopted = sup.adopt_sessions()
    assert adopted == []  # already mapped, tmux unchanged → neither re-adopted nor re-pointed
    rows = registry.read_valid_mapping(store_path=sup.store_path)
    assert len([r for r in rows if r.topic == "alpha"]) == 1  # exactly one row, no duplicate
    assert rows[0].tmux == "the-tmux"
