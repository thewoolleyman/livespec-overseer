"""Beside-tests for supervisor.py — remaining single branch.

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
import supervisor
from test_supervisor_builders import (
    TEST_EPIC,
    adopt_sup,
    idle_capture,
    isolate_store,
    make_plan,
    make_supervisor,
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
    assert supervisor.plan_epic_resume(repo=str(repo), epic=TEST_EPIC) in fake.paste_texts()
    assert [(r.topic, r.tmux) for r in registry.read_valid_mapping(store_path=store)] == [
        (topic, session)
    ]
    assert f"started {os.path.normpath(str(repo))}::{topic}" in capsys.readouterr().out


def test_live_outside_tmux_note_omits_the_suffix_when_no_status_is_reported(*, tmp_path):
    """The live-outside-tmux note appends Claude's own self-reported status only when the
    registry actually carries one. With none reported the note stops at the pid — never a
    dangling `self-reported status ` with nothing after it."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # mapped tmux session absent → routes to the no-managed-pane row
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(
        sessions_dir=sessions_dir, pid=100, name=topic, cwd=str(repo), status=""
    )  # no self-report
    sup = adopt_sup(
        tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={100: "pt"}
    )

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "live-outside-tmux"
    assert view.note == (
        "live Claude session (pid 100) running OUTSIDE tmux — daemon cannot manage it"
    )
    assert "self-reported status" not in view.note


def test_failed_paste_in_an_already_open_round_keeps_the_rounds_stamp(*, tmp_path):
    """The rollback on a failed wrap-up paste applies ONLY to a round this tick just
    OPENED. A re-warn at a lower band runs inside a round opened earlier, and clearing that
    round's `at` would reset the anchor `ready_valid` compares a declaration against — so
    the stamp is left alone and only the alert fires."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))  # a LOWER band than 50
    fake.paste_ok = False  # the re-warn paste does not land
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, warn_percent=50)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )  # round ALREADY open
    registry.add_notified_band(
        repo=str(repo), topic=topic, band=50, stamp_path=sup.stamp_path
    )  # the 50 band already sent
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert "wrap-up injection FAILED" in err.getvalue()
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )  # kept
    # The undelivered band is NOT marked notified, so the next tick re-tries it.
    assert 40 not in set(
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    )
