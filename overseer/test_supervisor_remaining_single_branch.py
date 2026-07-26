"""Beside-tests for supervisor.py — remaining single branch.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import os

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    idle_capture,
    isolate_store,
    make_plan,
    make_supervisor,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_window_badge_is_retried_when_the_rename_fails(*, tmp_path):
    """The badge is memoized so an unchanged count costs no tmux call — but only on
    SUCCESS. A rename that fails must not be remembered as written, or the attention count
    would be permanently absent from the window name until the count happened to change."""
    fake = FakeTmux()
    inner = fake.rename_window

    def failing_rename(*, pane, name):
        _ = inner(pane=pane, name=name)
        return False  # tmux refused the rename

    fake.rename_window = failing_rename
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, own_pane="%1")

    sup._refresh_window_name(attention=2)
    sup._refresh_window_name(attention=2)

    assert fake.renames() == ["overseer(2!)", "overseer(2!)"]  # retried, not memoized
    assert sup.last_window_name is None  # nothing recorded as written


def test_releasing_the_singleton_lock_frees_it_and_releasing_none_is_a_no_op(*, tmp_path):
    """Release must actually free the flock (else a daemon restart could never re-acquire
    its own store's lock), and must tolerate the `None` a contended acquire returns."""
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    handle = sup._acquire_singleton_lock()
    assert handle is not None

    supervisor.Supervisor._release_singleton_lock(handle=handle)

    regained = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())._acquire_singleton_lock()
    assert regained is not None  # the same store's lock is genuinely free again
    supervisor.Supervisor._release_singleton_lock(handle=regained)
    # Releasing a lock that was never acquired is a safe no-op, not a crash.
    assert supervisor.Supervisor._release_singleton_lock(handle=None) is None


def test_cli_start_respawns_a_session_proven_dead_by_its_bare_shell(
    *, tmp_path, monkeypatch, capsys
):
    """RB4: `start` fails CLOSED, refusing to respawn-kill anything not PROVEN dead. A bare
    SHELL is that proof (a live Claude reports `node`, a live Codex `bun`), so this is the
    one no-`--force` path that may respawn an EXISTING session."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fake = FakeTmux()
    # The session exists but its pane dropped to a shell — proven dead.
    fake.serve(session=session, repo=repo, capture=idle_capture(), cmd="zsh")
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 0

    assert fake.has(method="respawn")  # the dead shell's pane WAS relaunched
    assert not fake.has(method="new")  # ...in place; the session already existed
    assert supervisor.default_resume(repo=str(repo), topic=topic) in fake.paste_texts()
    assert [(r.topic, r.tmux) for r in registry.read_mapping(store_path=store)] == [
        (topic, session)
    ]
    assert f"started {os.path.normpath(str(repo))}::{topic}" in capsys.readouterr().out
