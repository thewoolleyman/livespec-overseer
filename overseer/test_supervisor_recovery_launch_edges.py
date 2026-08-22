"""Beside-tests for supervisor.py — reboot-recovery and launch edges.

Split from `test_supervisor_fail_soft_marker2.py` to keep the beside-test
modules below the LLOC margin while preserving the recovery fail-soft scenarios.

``import supervisor`` resolves via conftest.py.
"""

import pytest
import registry
from test_supervisor_builders import (
    codex_home_with,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Reboot-recovery edges: an already-live session is skipped, and every launch
# failure (Claude or Codex) is SURFACED rather than counted as recovered.
# --------------------------------------------------------------------------- #


def test_recover_skips_a_track_whose_session_is_already_live(*, tmp_path):
    """Recovery recreates only ABSENT sessions. A live one is skipped outright — the
    `session_exists` gate is what makes startup recovery safe to run at all."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture())  # the session IS live
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    assert sup.recover_missing_sessions() == []
    assert not fake.has(method="new")  # never re-created a live session...
    assert not fake.has(method="respawn")  # ...and never respawn-killed it


def test_recover_surfaces_a_claude_track_whose_launch_fails(*, tmp_path, capsys):
    """B5: `_do_launch` returning False must be SURFACED and the track left out of the
    recovered list — never a silent claim that a session was recreated."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # session absent → created, then the respawn fails
    fake.respawn_ok = False
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    assert sup.recover_missing_sessions() == []

    err = capsys.readouterr().err
    assert "reboot-recovery FAILED to launch" in err
    assert session in err and topic in err


def test_recover_codex_skips_when_new_session_does_not_create_the_session(*, tmp_path, capsys):
    """Codex re-review #3, Codex arm: if `new-session` did not create the EXACT session,
    recovery must not proceed to a respawn that could target a prefix-matched sibling."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fake = FakeTmux()
    fake.new_session_ok = False
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        codex_home=str(codex_home_with(tmp_path=tmp_path, topic=topic, session_id=sid)),
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    assert sup.recover_missing_sessions() == []
    assert not fake.has(method="respawn")

    err = capsys.readouterr().err
    assert "new-session did not create" in err and session in err


def test_recover_codex_surfaces_when_the_codex_resume_launch_fails(*, tmp_path, capsys):
    """B5, Codex arm: the session was created but `codex resume` never landed. The track
    is surfaced and NOT reported as recovered, so the operator relaunches it by hand."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fake = FakeTmux()
    fake.respawn_ok = False  # the session is created, but the codex respawn fails
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        codex_home=str(codex_home_with(tmp_path=tmp_path, topic=topic, session_id=sid)),
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    assert sup.recover_missing_sessions() == []
    assert fake.has(method="new")  # it got as far as creating the session...
    assert fake.has(method="respawn")  # ...and attempting the resume

    err = capsys.readouterr().err
    assert "FAILED to resume codex" in err and session in err


def test_launch_helpers_refuse_a_session_with_no_resolvable_pane(*, tmp_path):
    """RB3 for BOTH launch arms: with no pane id there is no exact target, so each helper
    returns False WITHOUT respawning — a bare `-t <name>` could hit a live sibling."""
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()  # no sessions at all → pane_id is None for anything
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session="no-such-session")

    assert sup.do_launch(track=track, session="no-such-session") is False
    assert (
        sup._do_codex_launch(track=track, session="no-such-session", session_id="aaaa-bbbb")
        is False
    )
    assert not fake.has(method="respawn")
